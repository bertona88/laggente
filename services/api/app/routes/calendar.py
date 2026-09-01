from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..calendar import (
    CalendarError,
    available_slots,
    build_google_authorization_url,
    create_booking,
    store_connection,
    verify_oauth_state,
)
from ..config import Settings
from ..database import get_db
from ..dependencies import (
    ProfessionalContext,
    authorize_public_conversation,
    current_professional,
    professional_space,
    runtime_settings,
)
from ..models import CalendarConnection, Event
from ..schemas import (
    CalendarAvailabilityOut,
    CalendarBookingCreate,
    CalendarBookingOut,
    CalendarConnectionOut,
    CalendarOAuthStartOut,
    CalendarSettingsUpdate,
    CalendarSlotOut,
    CalendarStatusOut,
)

router = APIRouter(tags=["calendar"])


def _owned_connection(
    db: Session, context: ProfessionalContext, space_id: str
) -> CalendarConnection | None:
    return db.scalar(
        select(CalendarConnection).where(
            CalendarConnection.account_id == context.account_id,
            CalendarConnection.space_id == space_id,
        )
    )


def _connection_out(connection: CalendarConnection) -> CalendarConnectionOut:
    return CalendarConnectionOut.model_validate(connection)


def _calendar_error(exc: CalendarError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/studio/calendar", response_model=CalendarStatusOut)
def calendar_status(
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
    settings: Settings = Depends(runtime_settings),
) -> CalendarStatusOut:
    space = professional_space(db, context)
    connection = _owned_connection(db, context, space.id)
    return CalendarStatusOut(
        available=settings.google_calendar_enabled,
        connection=_connection_out(connection) if connection else None,
    )


@router.post("/studio/calendar/oauth/start", response_model=CalendarOAuthStartOut)
def calendar_oauth_start(
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
    settings: Settings = Depends(runtime_settings),
) -> CalendarOAuthStartOut:
    professional_space(db, context)
    try:
        url = build_google_authorization_url(settings, context.member.id, context.account_id)
    except CalendarError as exc:
        raise _calendar_error(exc) from exc
    return CalendarOAuthStartOut(authorization_url=url)


@router.get("/studio/calendar/oauth/callback", include_in_schema=False)
def calendar_oauth_callback(
    request: Request,
    code: str = Query(min_length=1, max_length=4096),
    state: str = Query(min_length=20, max_length=4096),
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
    settings: Settings = Depends(runtime_settings),
):
    space = professional_space(db, context)
    try:
        verify_oauth_state(settings, state, context.member.id, context.account_id)
        tokens = request.app.state.calendar_gateway.exchange_code(code, settings)
        store_connection(
            db,
            settings,
            account_id=context.account_id,
            space_id=space.id,
            member_id=context.member.id,
            tokens=tokens,
        )
    except CalendarError:
        return RedirectResponse(
            f"{settings.app_origin.rstrip('/')}/studio/calendario?calendar=error",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        f"{settings.app_origin.rstrip('/')}/studio/calendario?calendar=connected",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.patch("/studio/calendar", response_model=CalendarConnectionOut)
def update_calendar_settings(
    body: CalendarSettingsUpdate,
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
) -> CalendarConnectionOut:
    space = professional_space(db, context)
    connection = _owned_connection(db, context, space.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Google Calendar non è collegato")
    try:
        ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Fuso orario non valido") from exc
    for key, value in body.model_dump().items():
        setattr(connection, key, value)
    db.add(
        Event(
            account_id=context.account_id,
            space_id=space.id,
            actor_type="professional",
            actor_id=context.member.id,
            event_type="calendar_booking_policy_updated",
            payload={"booking_enabled": body.booking_enabled},
        )
    )
    db.commit()
    db.refresh(connection)
    return _connection_out(connection)


@router.delete("/studio/calendar", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_calendar(
    db: Session = Depends(get_db),
    context: ProfessionalContext = Depends(current_professional),
):
    space = professional_space(db, context)
    connection = _owned_connection(db, context, space.id)
    if connection:
        db.add(
            Event(
                account_id=context.account_id,
                space_id=space.id,
                actor_type="professional",
                actor_id=context.member.id,
                event_type="google_calendar_disconnected",
            )
        )
        db.delete(connection)
        db.commit()


@router.get(
    "/public/conversations/{conversation_id}/calendar/availability",
    response_model=CalendarAvailabilityOut,
)
def public_calendar_availability(
    conversation_id: str,
    request: Request,
    start_date: date = Query(default_factory=date.today),
    days: int = Query(default=14, ge=1, le=31),
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> CalendarAvailabilityOut:
    conversation = authorize_public_conversation(request, db, conversation_id)
    request.app.state.rate_limiter.check(
        f"calendar-availability:{conversation.id}", limit=30, window_seconds=60 * 60
    )
    connection = db.scalar(
        select(CalendarConnection).where(
            CalendarConnection.account_id == conversation.account_id,
            CalendarConnection.space_id == conversation.space_id,
            CalendarConnection.status == "connected",
            CalendarConnection.booking_enabled.is_(True),
        )
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Prenotazione non disponibile")
    try:
        slots = available_slots(
            db,
            settings,
            request.app.state.calendar_gateway,
            connection,
            start_date=start_date,
            days=days,
        )
    except CalendarError as exc:
        raise _calendar_error(exc) from exc
    return CalendarAvailabilityOut(
        appointment_title=connection.appointment_title,
        location=connection.location,
        slots=[
            CalendarSlotOut(start=slot.start, end=slot.end, timezone=connection.timezone)
            for slot in slots
        ],
    )


@router.post(
    "/public/conversations/{conversation_id}/calendar/bookings",
    response_model=CalendarBookingOut,
)
def public_calendar_booking(
    conversation_id: str,
    body: CalendarBookingCreate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(runtime_settings),
) -> CalendarBookingOut:
    conversation = authorize_public_conversation(request, db, conversation_id)
    request.app.state.rate_limiter.check(
        f"calendar-booking:{conversation.id}", limit=8, window_seconds=60 * 60
    )
    connection = db.scalar(
        select(CalendarConnection).where(
            CalendarConnection.account_id == conversation.account_id,
            CalendarConnection.space_id == conversation.space_id,
            CalendarConnection.status == "connected",
            CalendarConnection.booking_enabled.is_(True),
        )
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Prenotazione non disponibile")
    if body.start.tzinfo is None:
        raise HTTPException(status_code=422, detail="L'orario deve includere il fuso orario")
    try:
        booking = create_booking(
            db,
            settings,
            request.app.state.calendar_gateway,
            connection,
            conversation_id=conversation.id,
            visitor_name=body.visitor_name,
            visitor_email=str(body.visitor_email),
            start=body.start,
        )
    except CalendarError as exc:
        raise _calendar_error(exc) from exc
    return CalendarBookingOut.model_validate(booking)

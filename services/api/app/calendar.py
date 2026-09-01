from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import Settings
from .models import CalendarBooking, CalendarConnection, Event, utcnow
from .security import TokenError, TokenSigner

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_CALENDAR_SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
)


class CalendarError(RuntimeError):
    pass


@dataclass(frozen=True)
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    email: str


@dataclass(frozen=True)
class CalendarSlot:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class CreatedCalendarEvent:
    event_id: str
    html_link: str | None


class CalendarGateway(Protocol):
    def exchange_code(self, code: str, settings: Settings) -> OAuthTokens: ...

    def refresh_access_token(self, refresh_token: str, settings: Settings) -> OAuthTokens: ...

    def busy_periods(
        self,
        access_token: str,
        *,
        start: datetime,
        end: datetime,
        timezone: str,
    ) -> list[tuple[datetime, datetime]]: ...

    def create_event(
        self,
        access_token: str,
        *,
        start: datetime,
        end: datetime,
        timezone: str,
        summary: str,
        description: str,
        location: str | None,
        attendee_email: str,
        attendee_name: str,
    ) -> CreatedCalendarEvent: ...


class GoogleCalendarGateway:
    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout_seconds = timeout_seconds

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            response = httpx.request(method, url, timeout=self.timeout_seconds, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, ValueError) as exc:
            raise CalendarError("Google Calendar non è raggiungibile in questo momento") from exc

    def exchange_code(self, code: str, settings: Settings) -> OAuthTokens:
        response = self._request(
            "POST",
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_calendar_client_id,
                "client_secret": settings.google_calendar_client_secret,
                "redirect_uri": settings.google_calendar_redirect_uri,
                "grant_type": "authorization_code",
            },
        ).json()
        access_token = str(response.get("access_token") or "")
        if not access_token:
            raise CalendarError("Google non ha restituito un token di accesso")
        userinfo = self._request(
            "GET",
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        email = str(userinfo.get("email") or "").strip().lower()
        if not email:
            raise CalendarError("Google non ha restituito l'indirizzo del calendario")
        return OAuthTokens(
            access_token=access_token,
            refresh_token=response.get("refresh_token"),
            expires_at=utcnow() + timedelta(seconds=max(int(response.get("expires_in", 3600)), 60)),
            email=email,
        )

    def refresh_access_token(self, refresh_token: str, settings: Settings) -> OAuthTokens:
        response = self._request(
            "POST",
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_calendar_client_id,
                "client_secret": settings.google_calendar_client_secret,
                "grant_type": "refresh_token",
            },
        ).json()
        access_token = str(response.get("access_token") or "")
        if not access_token:
            raise CalendarError("Google non ha rinnovato l'accesso al calendario")
        return OAuthTokens(
            access_token=access_token,
            refresh_token=None,
            expires_at=utcnow() + timedelta(seconds=max(int(response.get("expires_in", 3600)), 60)),
            email="",
        )

    def busy_periods(
        self,
        access_token: str,
        *,
        start: datetime,
        end: datetime,
        timezone: str,
    ) -> list[tuple[datetime, datetime]]:
        data = self._request(
            "POST",
            f"{GOOGLE_CALENDAR_API}/freeBusy",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "timeZone": timezone,
                "items": [{"id": "primary"}],
            },
        ).json()
        calendar = data.get("calendars", {}).get("primary", {})
        if calendar.get("errors"):
            raise CalendarError("Google non ha autorizzato la lettura della disponibilità")
        periods: list[tuple[datetime, datetime]] = []
        for item in calendar.get("busy", []):
            try:
                periods.append((datetime.fromisoformat(item["start"]), datetime.fromisoformat(item["end"])))
            except (KeyError, TypeError, ValueError):
                continue
        return periods

    def create_event(
        self,
        access_token: str,
        *,
        start: datetime,
        end: datetime,
        timezone: str,
        summary: str,
        description: str,
        location: str | None,
        attendee_email: str,
        attendee_name: str,
    ) -> CreatedCalendarEvent:
        payload = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": timezone},
            "attendees": [{"email": attendee_email, "displayName": attendee_name}],
            "guestsCanInviteOthers": False,
        }
        if location:
            payload["location"] = location
        data = self._request(
            "POST",
            f"{GOOGLE_CALENDAR_API}/calendars/primary/events?sendUpdates=all",
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload,
        ).json()
        event_id = str(data.get("id") or "")
        if not event_id:
            raise CalendarError("Google non ha confermato la creazione dell'appuntamento")
        return CreatedCalendarEvent(event_id=event_id, html_link=data.get("htmlLink"))


def build_google_authorization_url(settings: Settings, member_id: str, account_id: str) -> str:
    if not settings.google_calendar_enabled:
        raise CalendarError("Il collegamento a Google Calendar non è attivo")
    state = TokenSigner(settings.session_secret).issue(
        "google_calendar_oauth",
        10 * 60,
        member_id=member_id,
        account_id=account_id,
    )
    return f"{GOOGLE_AUTH_URL}?{urlencode({'client_id': settings.google_calendar_client_id, 'redirect_uri': settings.google_calendar_redirect_uri, 'response_type': 'code', 'scope': ' '.join(GOOGLE_CALENDAR_SCOPES), 'access_type': 'offline', 'include_granted_scopes': 'true', 'prompt': 'consent', 'state': state})}"


def verify_oauth_state(settings: Settings, state: str, member_id: str, account_id: str) -> None:
    try:
        payload = TokenSigner(settings.session_secret).verify(state, "google_calendar_oauth")
    except TokenError as exc:
        raise CalendarError("Collegamento Google scaduto o non valido") from exc
    if payload.get("member_id") != member_id or payload.get("account_id") != account_id:
        raise CalendarError("Il collegamento Google appartiene a un altro account")


def _fernet(settings: Settings) -> Fernet:
    secret = settings.google_calendar_encryption_key or settings.session_secret
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(settings: Settings, token: str) -> bytes:
    return _fernet(settings).encrypt(token.encode("utf-8"))


def decrypt_token(settings: Settings, token: bytes) -> str:
    try:
        return _fernet(settings).decrypt(token).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise CalendarError("Le credenziali del calendario non sono leggibili") from exc


def access_token(
    db: Session,
    settings: Settings,
    gateway: CalendarGateway,
    connection: CalendarConnection,
) -> str:
    expires_at = connection.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if connection.access_token_encrypted and expires_at > utcnow() + timedelta(minutes=2):
        return decrypt_token(settings, connection.access_token_encrypted)
    refreshed = gateway.refresh_access_token(
        decrypt_token(settings, connection.refresh_token_encrypted), settings
    )
    connection.access_token_encrypted = encrypt_token(settings, refreshed.access_token)
    connection.token_expires_at = refreshed.expires_at
    db.commit()
    return refreshed.access_token


def store_connection(
    db: Session,
    settings: Settings,
    *,
    account_id: str,
    space_id: str,
    member_id: str,
    tokens: OAuthTokens,
) -> CalendarConnection:
    connection = db.scalar(
        select(CalendarConnection).where(
            CalendarConnection.account_id == account_id,
            CalendarConnection.space_id == space_id,
        )
    )
    if connection is None:
        if not tokens.refresh_token:
            raise CalendarError("Google non ha restituito l'accesso permanente al calendario")
        connection = CalendarConnection(
            account_id=account_id,
            space_id=space_id,
            connected_by_member_id=member_id,
            provider_email=tokens.email,
            refresh_token_encrypted=encrypt_token(settings, tokens.refresh_token),
            access_token_encrypted=encrypt_token(settings, tokens.access_token),
            token_expires_at=tokens.expires_at,
        )
        db.add(connection)
    else:
        connection.connected_by_member_id = member_id
        connection.provider_email = tokens.email
        connection.access_token_encrypted = encrypt_token(settings, tokens.access_token)
        connection.token_expires_at = tokens.expires_at
        if tokens.refresh_token:
            connection.refresh_token_encrypted = encrypt_token(settings, tokens.refresh_token)
        connection.status = "connected"
    db.flush()
    db.add(
        Event(
            account_id=account_id,
            space_id=space_id,
            actor_type="professional",
            actor_id=member_id,
            event_type="google_calendar_connected",
            payload={"provider_email": tokens.email},
        )
    )
    db.commit()
    db.refresh(connection)
    return connection


def _timezone(connection: CalendarConnection) -> ZoneInfo:
    try:
        return ZoneInfo(connection.timezone)
    except ZoneInfoNotFoundError as exc:
        raise CalendarError("Fuso orario del calendario non valido") from exc


def _parse_clock(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise CalendarError("Orario di prenotazione non valido") from exc


def available_slots(
    db: Session,
    settings: Settings,
    gateway: CalendarGateway,
    connection: CalendarConnection,
    *,
    start_date: date,
    days: int,
    limit: int = 24,
) -> list[CalendarSlot]:
    if connection.status != "connected" or not connection.booking_enabled:
        return []
    zone = _timezone(connection)
    window_start = datetime.combine(start_date, time.min, zone)
    window_end = window_start + timedelta(days=days)
    busy = gateway.busy_periods(
        access_token(db, settings, gateway, connection),
        start=window_start,
        end=window_end,
        timezone=connection.timezone,
    )
    local_bookings = db.scalars(
        select(CalendarBooking).where(
            CalendarBooking.account_id == connection.account_id,
            CalendarBooking.calendar_connection_id == connection.id,
            CalendarBooking.start_at < window_end,
            CalendarBooking.end_at > window_start,
        )
    ).all()
    for booking in local_bookings:
        booking_start = booking.start_at
        booking_end = booking.end_at
        if booking_start.tzinfo is None:
            booking_start = booking_start.replace(tzinfo=zone)
        if booking_end.tzinfo is None:
            booking_end = booking_end.replace(tzinfo=zone)
        busy.append((booking_start, booking_end))
    now_floor = datetime.now(zone) + timedelta(minutes=connection.minimum_notice_minutes)
    duration = timedelta(minutes=connection.duration_minutes)
    buffer = timedelta(minutes=connection.buffer_minutes)
    result: list[CalendarSlot] = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        if day.weekday() not in connection.work_days:
            continue
        cursor = datetime.combine(day, _parse_clock(connection.day_start), zone)
        day_end = datetime.combine(day, _parse_clock(connection.day_end), zone)
        while cursor + duration <= day_end:
            slot_end = cursor + duration
            blocked = any(cursor < busy_end + buffer and slot_end + buffer > busy_start for busy_start, busy_end in busy)
            if cursor >= now_floor and not blocked:
                result.append(CalendarSlot(start=cursor, end=slot_end))
                if len(result) >= limit:
                    return result
            cursor += timedelta(minutes=connection.slot_interval_minutes)
    return result


def create_booking(
    db: Session,
    settings: Settings,
    gateway: CalendarGateway,
    connection: CalendarConnection,
    *,
    conversation_id: str,
    visitor_name: str,
    visitor_email: str,
    start: datetime,
) -> CalendarBooking:
    normalized_email = visitor_email.strip().lower()
    key_material = f"{connection.account_id}:{conversation_id}:{start.isoformat()}:{normalized_email}"
    idempotency_key = hashlib.sha256(key_material.encode()).hexdigest()
    existing = db.scalar(
        select(CalendarBooking).where(
            CalendarBooking.account_id == connection.account_id,
            CalendarBooking.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.status == "confirmed":
            return existing
        raise CalendarError(
            "Esiste già un tentativo non confermato per questo orario; verifica il calendario prima di riprovare"
        )
    slots = available_slots(
        db,
        settings,
        gateway,
        connection,
        start_date=start.astimezone(_timezone(connection)).date(),
        days=1,
        limit=96,
    )
    matching = next((slot for slot in slots if slot.start == start.astimezone(_timezone(connection))), None)
    if matching is None:
        raise CalendarError("Questo orario non è più disponibile")
    booking = CalendarBooking(
        account_id=connection.account_id,
        space_id=connection.space_id,
        conversation_id=conversation_id,
        calendar_connection_id=connection.id,
        visitor_name=visitor_name.strip(),
        visitor_email=normalized_email,
        start_at=matching.start,
        end_at=matching.end,
        timezone=connection.timezone,
        status="creating",
        provider_event_id=None,
        provider_event_link=None,
        idempotency_key=idempotency_key,
    )
    db.add(booking)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raced = db.scalar(
            select(CalendarBooking).where(
                CalendarBooking.account_id == connection.account_id,
                CalendarBooking.idempotency_key == idempotency_key,
            )
        )
        if raced and raced.status == "confirmed":
            return raced
        raise CalendarError("La prenotazione di questo orario è già in elaborazione o confermata")
    try:
        event = gateway.create_event(
            access_token(db, settings, gateway, connection),
            start=matching.start,
            end=matching.end,
            timezone=connection.timezone,
            summary=connection.appointment_title,
            description=(
                "Appuntamento prenotato nella conversazione LAGGENTE. "
                f"Riferimento conversazione: {conversation_id}"
            ),
            location=connection.location,
            attendee_email=normalized_email,
            attendee_name=visitor_name.strip(),
        )
    except CalendarError:
        booking.status = "failed"
        db.commit()
        raise
    booking.status = "confirmed"
    booking.provider_event_id = event.event_id
    booking.provider_event_link = event.html_link
    db.add(
        Event(
            account_id=connection.account_id,
            space_id=connection.space_id,
            conversation_id=conversation_id,
            actor_type="visitor",
            event_type="calendar_appointment_booked",
            payload={"booking_id": booking.id, "start_at": matching.start.isoformat()},
        )
    )
    db.commit()
    db.refresh(booking)
    return booking

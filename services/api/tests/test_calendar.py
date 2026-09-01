from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.calendar import CreatedCalendarEvent, OAuthTokens, decrypt_token
from app.config import Settings
from app.main import create_app
from app.models import CalendarBooking, CalendarConnection, Event


class FakeCalendarGateway:
    def __init__(self):
        self.created: list[dict] = []
        self.busy: list[tuple[datetime, datetime]] = []

    def exchange_code(self, code: str, settings: Settings) -> OAuthTokens:
        assert code == "oauth-code"
        return OAuthTokens(
            access_token="access-secret",
            refresh_token="refresh-secret",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            email="mauro@example.com",
        )

    def refresh_access_token(self, refresh_token: str, settings: Settings) -> OAuthTokens:
        assert refresh_token == "refresh-secret"
        return OAuthTokens(
            access_token="refreshed-secret",
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            email="",
        )

    def busy_periods(self, access_token: str, **kwargs):
        assert access_token in {"access-secret", "refreshed-secret"}
        return self.busy

    def create_event(self, access_token: str, **kwargs):
        self.created.append(kwargs)
        return CreatedCalendarEvent(event_id=f"google-{len(self.created)}", html_link=None)


def calendar_client(settings: Settings):
    enabled = settings.model_copy(
        update={
            "google_calendar_enabled": True,
            "google_calendar_client_id": "client-id.apps.googleusercontent.com",
            "google_calendar_client_secret": "client-secret",
            "google_calendar_redirect_uri": (
                "https://app.laggente.com/api/v1/studio/calendar/oauth/callback"
            ),
            "google_calendar_encryption_key": "k" * 48,
        }
    )
    app = create_app(enabled)
    gateway = FakeCalendarGateway()
    app.state.calendar_gateway = gateway
    return enabled, gateway, TestClient(app)


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/pilot-login",
        json={"email": "mauro@laggente.com", "password": "password-pilot-molto-sicura"},
    )
    assert response.status_code == 200


def connect(client: TestClient) -> None:
    start = client.post("/api/v1/studio/calendar/oauth/start")
    assert start.status_code == 200
    authorization_url = start.json()["authorization_url"]
    query = parse_qs(urlparse(authorization_url).query)
    assert query["scope"][0].split() == [
        "openid",
        "email",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.freebusy",
    ]
    callback = client.get(
        "/api/v1/studio/calendar/oauth/callback",
        params={"code": "oauth-code", "state": query["state"][0]},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"].endswith("/studio/calendario?calendar=connected")


def next_weekday(target: int) -> date:
    candidate = date.today() + timedelta(days=2)
    while candidate.weekday() != target:
        candidate += timedelta(days=1)
    return candidate


def test_calendar_is_disabled_by_default(professional_client):
    assert professional_client.get("/api/v1/studio/calendar").json() == {
        "available": False,
        "connection": None,
    }
    response = professional_client.post("/api/v1/studio/calendar/oauth/start")
    assert response.status_code == 409


def test_oauth_tokens_are_encrypted_and_connection_is_tenant_owned(settings):
    enabled, _, client = calendar_client(settings)
    with client:
        login(client)
        connect(client)
        response = client.get("/api/v1/studio/calendar")
        assert response.status_code == 200
        assert response.json()["connection"]["provider_email"] == "mauro@example.com"

        with database.SessionLocal() as db:
            connection = db.scalar(select(CalendarConnection))
            assert connection is not None
            assert b"refresh-secret" not in connection.refresh_token_encrypted
            assert b"access-secret" not in connection.access_token_encrypted
            assert decrypt_token(enabled, connection.refresh_token_encrypted) == "refresh-secret"
            assert db.scalar(
                select(Event).where(Event.event_type == "google_calendar_connected")
            )


def test_public_availability_and_booking_are_real_idempotent_and_conversation_scoped(settings):
    _, gateway, client = calendar_client(settings)
    with client:
        login(client)
        connect(client)
        update = client.patch(
            "/api/v1/studio/calendar",
            json={
                "booking_enabled": True,
                "timezone": "Europe/Rome",
                "work_days": [0, 1, 2, 3, 4],
                "day_start": "09:00",
                "day_end": "11:00",
                "duration_minutes": 30,
                "slot_interval_minutes": 30,
                "buffer_minutes": 0,
                "minimum_notice_minutes": 0,
                "appointment_title": "Valutazione immobile",
                "location": "Agenzia",
            },
        )
        assert update.status_code == 200

        created = client.post("/api/v1/public/mauro/conversations", json={}).json()
        conversation_id = created["conversation"]["id"]
        token = created["continuation_token"]
        headers = {"X-Conversation-Token": token}
        monday = next_weekday(0)
        availability = client.get(
            f"/api/v1/public/conversations/{conversation_id}/calendar/availability",
            params={"start_date": monday.isoformat(), "days": 1},
            headers=headers,
        )
        assert availability.status_code == 200, availability.text
        body = availability.json()
        assert body["appointment_title"] == "Valutazione immobile"
        assert len(body["slots"]) == 4
        selected = body["slots"][0]["start"]

        denied = client.get(
            f"/api/v1/public/conversations/{conversation_id}/calendar/availability",
            params={"start_date": monday.isoformat(), "days": 1},
            headers={"X-Conversation-Token": "wrong-token"},
        )
        assert denied.status_code == 404

        payload = {
            "visitor_name": "Giulia Verdi",
            "visitor_email": "giulia@example.com",
            "start": selected,
        }
        first = client.post(
            f"/api/v1/public/conversations/{conversation_id}/calendar/bookings",
            json=payload,
            headers=headers,
        )
        second = client.post(
            f"/api/v1/public/conversations/{conversation_id}/calendar/bookings",
            json=payload,
            headers=headers,
        )
        assert first.status_code == second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        assert len(gateway.created) == 1
        assert gateway.created[0]["attendee_email"] == "giulia@example.com"

        competing = client.post(
            f"/api/v1/public/conversations/{conversation_id}/calendar/bookings",
            json={**payload, "visitor_email": "altra@example.com"},
            headers=headers,
        )
        assert competing.status_code == 409
        assert len(gateway.created) == 1

        with database.SessionLocal() as db:
            assert len(db.scalars(select(CalendarBooking)).all()) == 1
            assert db.scalar(
                select(Event).where(Event.event_type == "calendar_appointment_booked")
            )

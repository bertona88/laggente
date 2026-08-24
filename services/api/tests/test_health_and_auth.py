from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app import database
from app.config import Settings
from app.database import Base
from app.main import create_app
from app.models import Event, Member


def test_health_readiness_and_version(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}
    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/health/ready").status_code == 200
    version = client.get("/api/v1/version").json()
    assert version["service"] == "laggente-api"
    assert version["version"]


def test_tenant_subdomain_localhost_is_allowed_for_vite_development(client):
    response = client.get("/healthz", headers={"Host": "mauro.localhost:3000"})
    assert response.status_code == 200


def test_pilot_password_session_is_host_only_and_protected(client):
    assert client.get("/api/v1/auth/session").status_code == 401
    bad = client.post(
        "/api/v1/auth/pilot-login",
        json={"email": "mauro@laggente.com", "password": "wrong"},
    )
    assert bad.status_code == 401
    response = client.post(
        "/api/v1/auth/pilot-login",
        json={"email": "mauro@laggente.com", "password": "password-pilot-molto-sicura"},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Domain=" not in cookie
    assert client.get("/api/v1/auth/session").json()["member"]["role"] == "professional"
    denied = client.post(
        "/api/v1/studio/messages",
        headers={"Origin": "https://mauro.laggente.com"},
        json={"content": "Ciao"},
    )
    assert denied.status_code == 403
    allowed = client.post(
        "/api/v1/studio/messages",
        headers={"Origin": "https://app.laggente.com"},
        json={"content": "Ciao dallo Studio", "client_message_id": "cors-attempt-1"},
    )
    assert allowed.status_code == 200
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401


def test_magic_link_is_signed_expiring_and_single_use(tmp_path):
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'magic.db'}",
        SESSION_SECRET="m" * 48,
        AUTH_MODE="magic_link",
        PILOT_EMAIL="mauro@laggente.com",
        PILOT_PASSWORD=None,
        OPENAI_API_KEY=None,
        UPLOAD_DIR=tmp_path / "uploads",
        TRUSTED_HOSTS="testserver",
    )
    with TestClient(create_app(settings)) as client:
        requested = client.post(
            "/api/v1/auth/magic-link/request", json={"email": "mauro@laggente.com"}
        )
        assert requested.status_code == 200
        link = requested.json()["development_magic_link"]
        assert urlparse(link).path == "/login"
        assert urlparse(link).query == ""
        token = parse_qs(urlparse(link).fragment)["token"][0]
        first = client.post("/api/v1/auth/magic-link/consume", json={"token": token})
        assert first.status_code == 200
        second = client.post("/api/v1/auth/magic-link/consume", json={"token": token})
        assert second.status_code == 401
        tampered = client.post(
            "/api/v1/auth/magic-link/consume", json={"token": token[:-1] + "x"}
        )
        assert tampered.status_code == 401


def test_magic_link_concurrent_consumption_issues_exactly_one_session(tmp_path):
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'magic-concurrent.db'}",
        SESSION_SECRET="c" * 48,
        AUTH_MODE="magic_link",
        PILOT_EMAIL="mauro@laggente.com",
        PILOT_PASSWORD=None,
        OPENAI_API_KEY=None,
        UPLOAD_DIR=tmp_path / "uploads-concurrent",
        TRUSTED_HOSTS="testserver",
    )
    with TestClient(create_app(settings)) as client:
        requested = client.post(
            "/api/v1/auth/magic-link/request", json={"email": "mauro@laggente.com"}
        )
        assert requested.status_code == 200
        link = requested.json()["development_magic_link"]
        token = parse_qs(urlparse(link).fragment)["token"][0]

        update_barrier = Barrier(2)

        def align_magic_link_updates(
            _connection, _cursor, statement, _parameters, _context, _executemany
        ):
            if statement.lstrip().lower().startswith("update magic_links"):
                update_barrier.wait(timeout=5)

        event.listen(database.engine, "before_cursor_execute", align_magic_link_updates)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(
                    pool.map(
                        lambda _: client.post(
                            "/api/v1/auth/magic-link/consume", json={"token": token}
                        ),
                        range(2),
                    )
                )
        finally:
            event.remove(database.engine, "before_cursor_execute", align_magic_link_updates)

        assert sorted(response.status_code for response in responses) == [200, 401]
        assert sum("set-cookie" in response.headers for response in responses) == 1
        with database.SessionLocal() as db:
            session_started_count = db.scalar(
                select(func.count(Event.id)).where(Event.event_type == "studio_session_started")
            )
        assert session_started_count == 1


def test_password_backed_member_can_recover_with_a_magic_link_in_pilot_mode(client):
    assert client.get("/api/v1/auth/mode").json() == {"mode": "pilot_password"}
    response = client.post(
        "/api/v1/auth/magic-link/request", json={"email": "mauro@laggente.com"}
    )
    assert response.status_code == 200
    link = response.json()["development_magic_link"]
    assert urlparse(link).path == "/login"
    token = parse_qs(urlparse(link).fragment)["token"][0]
    consumed = client.post("/api/v1/auth/magic-link/consume", json={"token": token})
    assert consumed.status_code == 200


def test_magic_link_request_serves_existing_members_and_new_professionals(client):
    known = client.post(
        "/api/v1/auth/magic-link/request", json={"email": "mauro@laggente.com"}
    )
    unknown = client.post(
        "/api/v1/auth/magic-link/request", json={"email": "unknown@example.com"}
    )

    assert known.status_code == unknown.status_code == 200
    assert known.json()["accepted"] is unknown.json()["accepted"] is True
    assert known.json()["message"] == unknown.json()["message"]
    assert "entrare o creare" in known.json()["message"]
    assert parse_qs(urlparse(known.json()["development_magic_link"]).fragment)["token"]
    assert parse_qs(urlparse(unknown.json()["development_magic_link"]).fragment)["signup"]
    with database.SessionLocal() as db:
        assert db.scalar(
            select(func.count(Member.id)).where(Member.email == "unknown@example.com")
        ) == 0


def test_production_requires_transactional_email_for_professional_access():
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        SESSION_SECRET="p" * 48,
        AUTH_MODE="pilot_password",
        PILOT_PASSWORD="password-pilot-molto-sicura",
        COOKIE_SECURE=True,
        AUTO_CREATE_SCHEMA=False,
        RESEND_API_KEY=None,
        FROM_EMAIL=None,
    )
    with pytest.raises(RuntimeError, match="professional email access"):
        settings.validate_runtime()


def test_production_cors_excludes_public_tenant_origins(tmp_path):
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        DATABASE_URL=f"sqlite:///{tmp_path / 'cors.db'}",
        SESSION_SECRET="p" * 48,
        AUTH_MODE="pilot_password",
        PILOT_PASSWORD="password-pilot-molto-sicura",
        RESEND_API_KEY="re_test_key",
        FROM_EMAIL="LAGGENTE <studio@laggente.com>",
        COOKIE_SECURE=True,
        AUTO_CREATE_SCHEMA=False,
        SEED_DEMO=False,
        APP_ORIGIN="https://app.laggente.com",
        CORS_ORIGINS="https://app.laggente.com,https://mauro.laggente.com,https://laggente.com",
        UPLOAD_DIR=tmp_path / "uploads",
    )
    assert settings.api_cors_origin_list == ["https://app.laggente.com"]
    application = create_app(settings)
    Base.metadata.create_all(database.engine)
    with TestClient(application) as production_client:
        preflight = production_client.options(
            "/api/v1/studio/space",
            headers={
                "Host": "app.laggente.com",
                "Origin": "https://mauro.laggente.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code == 400
        assert "access-control-allow-origin" not in preflight.headers
        hostile_get = production_client.get(
            "/api/v1/studio/space",
            headers={
                "Host": "app.laggente.com",
                "Origin": "https://mauro.laggente.com",
            },
        )
        assert hostile_get.status_code == 401
        assert "access-control-allow-origin" not in hostile_get.headers
        app_get = production_client.get(
            "/api/v1/studio/space",
            headers={
                "Host": "app.laggente.com",
                "Origin": "https://app.laggente.com",
            },
        )
        assert app_get.status_code == 401
        assert app_get.headers["access-control-allow-origin"] == "https://app.laggente.com"

        assert production_client.get(
            "/api/v1/auth/mode", headers={"Host": "app.laggente.com"}
        ).status_code == 200
        wrong_host_login = production_client.post(
            "/api/v1/auth/pilot-login",
            headers={"Host": "mauro.laggente.com"},
            json={"email": "mauro@laggente.com", "password": "password-pilot-molto-sicura"},
        )
        assert wrong_host_login.status_code == 404
        assert "set-cookie" not in wrong_host_login.headers
        assert production_client.get(
            "/api/v1/studio/space", headers={"Host": "mauro.laggente.com"}
        ).status_code == 404

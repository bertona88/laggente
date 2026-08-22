from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status

from .config import Settings


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class TokenError(ValueError):
    pass


class TokenSigner:
    def __init__(self, secret: str):
        self._secret = secret.encode("utf-8")

    def issue(self, purpose: str, ttl_seconds: int, **claims: Any) -> str:
        now = int(datetime.now(UTC).timestamp())
        payload = {"p": purpose, "iat": now, "exp": now + ttl_seconds, "n": secrets.token_urlsafe(12)}
        payload.update(claims)
        encoded = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
        signature = _b64encode(hmac.new(self._secret, encoded.encode(), hashlib.sha256).digest())
        return f"{encoded}.{signature}"

    def verify(self, token: str, purpose: str) -> dict[str, Any]:
        try:
            encoded, signature = token.split(".", 1)
            expected = _b64encode(
                hmac.new(self._secret, encoded.encode(), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(signature, expected):
                raise TokenError("invalid signature")
            payload = json.loads(_b64decode(encoded))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise TokenError("malformed token") from exc
        if payload.get("p") != purpose:
            raise TokenError("wrong token purpose")
        if not isinstance(payload.get("exp"), int) or payload["exp"] < int(datetime.now(UTC).timestamp()):
            raise TokenError("expired token")
        return payload


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_ip(value: str | None, secret: str) -> str | None:
    if not value:
        return None
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def hash_password(password: str, *, iterations: int = 600_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations, salt, digest = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _b64decode(salt), int(iterations)
        )
        return hmac.compare_digest(_b64encode(actual), digest)
    except (TypeError, ValueError):
        return False


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class SessionClaims:
    member_id: str
    account_id: str


def issue_session_token(settings: Settings, member_id: str, account_id: str) -> str:
    return TokenSigner(settings.session_secret).issue(
        "studio_session",
        settings.session_ttl_seconds,
        member_id=member_id,
        account_id=account_id,
    )


def read_session_claims(request: Request, settings: Settings) -> SessionClaims:
    token = request.cookies.get(settings.studio_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Accesso richiesto")
    try:
        payload = TokenSigner(settings.session_secret).verify(token, "studio_session")
        return SessionClaims(member_id=payload["member_id"], account_id=payload["account_id"])
    except (TokenError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione non valida")


def set_session_cookie(response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.studio_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )

def clear_session_cookie(response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.studio_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )

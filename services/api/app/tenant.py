from __future__ import annotations

import re

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import Space


SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
RESERVED_SLUGS = {"app", "api", "www", "admin", "mail", "static", "assets", "blog", "support"}


def normalize_slug(value: str) -> str:
    slug = value.strip().lower().rstrip(".")
    if not SLUG_RE.fullmatch(slug) or slug in RESERVED_SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spazio non trovato")
    return slug


def slug_from_host(request: Request, settings: Settings) -> str:
    host = request.headers.get("host", "").split(":", 1)[0].lower().rstrip(".")
    suffix = f".{settings.base_domain.lower()}"
    if not host.endswith(suffix):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spazio non trovato")
    return normalize_slug(host[: -len(suffix)])


def require_public_space_host(request: Request, settings: Settings, space: Space) -> None:
    """Bind a public operation to the hostname that owns the space and visitor cookie.

    Local/test path-based routing remains available on loopback and ``testserver``. Any request
    using the real base domain, and every production request, must use the canonical tenant host.
    """

    host = request.headers.get("host", "").split(":", 1)[0].lower().rstrip(".")
    expected = f"{space.slug}.{settings.base_domain.lower()}"
    local_host = host in {"localhost", "127.0.0.1", "testserver"} or host.endswith(".localhost")
    if host == expected:
        return
    if not settings.is_production and local_host:
        return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spazio non trovato")


def resolve_public_space(db: Session, slug: str) -> Space:
    normalized = normalize_slug(slug)
    space = db.scalar(select(Space).where(Space.slug == normalized, Space.is_active.is_(True)))
    if not space or not space.active_revision_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spazio non trovato")
    return space

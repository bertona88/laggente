from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    # Database exceptions can reach application stderr. Never interpolate private messages,
    # configuration documents, filenames, tokens, or other bound values into those errors.
    return create_engine(
        database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args=connect_args,
    )


settings = get_settings()
engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def configure_database(runtime_settings: Settings) -> None:
    """Rebind globals for app factories and isolated tests."""
    global engine, SessionLocal
    engine = build_engine(runtime_settings.database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

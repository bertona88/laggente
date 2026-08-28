from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .positioning import load_product_positioning


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", "../../.env.local", "services/api/.env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(default="sqlite:///./laggente.db", alias="DATABASE_URL")
    session_secret: str = Field(default="development-only-change-me", alias="SESSION_SECRET")
    base_domain: str = Field(default="laggente.com", alias="BASE_DOMAIN")
    app_origin: str = Field(default="http://localhost:3000", alias="APP_ORIGIN")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,https://app.laggente.com",
        alias="CORS_ORIGINS",
    )
    trusted_hosts: str = Field(
        default="localhost,*.localhost,127.0.0.1,testserver,laggente.com,*.laggente.com",
        alias="TRUSTED_HOSTS",
    )
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")
    session_ttl_seconds: int = Field(default=60 * 60 * 24 * 14, alias="SESSION_TTL_SECONDS")
    magic_link_ttl_seconds: int = Field(default=15 * 60, alias="MAGIC_LINK_TTL_SECONDS")
    invitation_ttl_seconds: int = Field(
        default=7 * 24 * 60 * 60,
        ge=15 * 60,
        le=30 * 24 * 60 * 60,
        alias="INVITATION_TTL_SECONDS",
    )
    auth_mode: str = Field(default="pilot_password", alias="AUTH_MODE")
    pilot_email: str = Field(default="mauro@laggente.com", alias="PILOT_EMAIL")
    pilot_password: str | None = Field(default=None, alias="PILOT_PASSWORD")
    pilot_name: str = Field(default="Mauro Rossi", alias="PILOT_NAME")
    product_positioning_json: str | None = Field(default=None, alias="PRODUCT_POSITIONING_JSON")
    seed_demo: bool = Field(default=True, alias="SEED_DEMO")
    auto_create_schema: bool = Field(default=True, alias="AUTO_CREATE_SCHEMA")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.6", alias="OPENAI_MODEL")
    openai_transcription_model: str = Field(
        default="gpt-4o-mini-transcribe", alias="OPENAI_TRANSCRIPTION_MODEL"
    )
    openai_max_turns: int = Field(default=6, alias="OPENAI_MAX_TURNS")
    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")
    resend_webhook_secret: str | None = Field(default=None, alias="RESEND_WEBHOOK_SECRET")
    from_email: str | None = Field(default=None, alias="FROM_EMAIL")
    agent_mail_enabled: bool = Field(default=False, alias="AGENT_MAIL_ENABLED")
    agent_mail_provider: str = Field(default="capture", alias="AGENT_MAIL_PROVIDER")
    agent_mail_from_domain: str = Field(default="laggente.com", alias="AGENT_MAIL_FROM_DOMAIN")
    agent_mail_reply_domain: str = Field(
        default="inbound.laggente.com", alias="AGENT_MAIL_REPLY_DOMAIN"
    )
    agent_mail_aws_region: str = Field(default="eu-south-1", alias="AGENT_MAIL_AWS_REGION")
    agent_mail_inbound_secret: str | None = Field(
        default=None, alias="AGENT_MAIL_INBOUND_SECRET"
    )
    agent_mail_max_inbound_bytes: int = Field(
        default=5 * 1024 * 1024,
        ge=1024,
        le=25 * 1024 * 1024,
        alias="AGENT_MAIL_MAX_INBOUND_BYTES",
    )
    outreach_enabled: bool = Field(default=False, alias="OUTREACH_ENABLED")
    outreach_max_recipients: int = Field(
        default=5, ge=1, le=20, alias="OUTREACH_MAX_RECIPIENTS"
    )
    outreach_candidate_retention_days: int = Field(
        default=30, ge=1, le=90, alias="OUTREACH_CANDIDATE_RETENTION_DAYS"
    )
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_session_token: str | None = Field(default=None, alias="AWS_SESSION_TOKEN")
    upload_dir: Path = Field(default=Path("./data/uploads"), alias="UPLOAD_DIR")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    conversation_retention_days: int = Field(
        default=365, ge=1, le=3650, alias="CONVERSATION_RETENTION_DAYS"
    )
    privacy_notice_version: str = Field(
        default="2026-08-27.1", min_length=1, max_length=50, alias="PRIVACY_NOTICE_VERSION"
    )
    version: str = Field(default="0.1.0", alias="APP_VERSION")
    git_sha: str = Field(default="unknown", alias="GIT_SHA")

    @field_validator("app_env", "auth_mode", "agent_mail_provider")
    @classmethod
    def normalize_env(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("agent_mail_from_domain", "agent_mail_reply_domain")
    @classmethod
    def normalize_mail_domain(cls, value: str) -> str:
        domain = value.strip().lower().rstrip(".")
        labels = domain.split(".")
        if (
            len(domain) > 253
            or len(labels) < 2
            or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or any(not (character.isalnum() or character == "-") for character in label)
                for label in labels
            )
        ):
            raise ValueError("Agent mail domain is invalid")
        return domain

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.cors_origins.split(",") if item.strip()]

    @property
    def api_cors_origin_list(self) -> list[str]:
        # Production is same-origin through the nginx gateway. Tenant origins never need credentialed
        # cross-origin access to Studio data or mutations.
        if self.is_production:
            return [self.app_origin.rstrip("/")]
        return self.cors_origin_list

    @property
    def trusted_host_list(self) -> list[str]:
        return [item.strip().lower() for item in self.trusted_hosts.split(",") if item.strip()]

    @property
    def studio_cookie_name(self) -> str:
        return "__Host-laggente_studio" if self.cookie_secure else "laggente_studio"

    @property
    def visitor_cookie_name(self) -> str:
        return "__Host-laggente_visitor" if self.cookie_secure else "laggente_visitor"

    def validate_runtime(self) -> None:
        # Product focus is backend-owned and must fail closed before serving inconsistent copy or
        # assistant guidance. Operators can change weights and examples without rebuilding the SPA.
        load_product_positioning(self.product_positioning_json)
        if self.agent_mail_enabled:
            if self.agent_mail_provider not in {"capture", "resend", "ses"}:
                raise RuntimeError("AGENT_MAIL_PROVIDER must be capture, resend, or ses")
            if not self.agent_mail_from_domain or not self.agent_mail_reply_domain:
                raise RuntimeError("Agent mail sender and reply domains are required")
            if self.agent_mail_provider == "resend" and (
                not self.resend_api_key or not self.resend_webhook_secret
            ):
                raise RuntimeError(
                    "RESEND_API_KEY and RESEND_WEBHOOK_SECRET are required for Resend agent mail"
                )
            if self.agent_mail_provider == "ses" and (
                not self.agent_mail_inbound_secret
                or len(self.agent_mail_inbound_secret) < 32
            ):
                raise RuntimeError(
                    "AGENT_MAIL_INBOUND_SECRET must contain at least 32 characters "
                    "for the SES inbound relay"
                )
        if self.outreach_enabled and not self.agent_mail_enabled:
            raise RuntimeError("OUTREACH_ENABLED requires AGENT_MAIL_ENABLED")
        if self.is_production:
            if self.session_secret == "development-only-change-me" or len(self.session_secret) < 32:
                raise RuntimeError("SESSION_SECRET must be a strong, project-specific value in production")
            if not self.cookie_secure:
                raise RuntimeError("COOKIE_SECURE must be true in production")
            if self.auto_create_schema:
                raise RuntimeError("AUTO_CREATE_SCHEMA must be false in production; use Alembic")
            if not self.resend_api_key or not self.from_email:
                raise RuntimeError(
                    "RESEND_API_KEY and FROM_EMAIL are required for professional email access"
                )
            if self.auth_mode == "pilot_password":
                if not self.pilot_password or len(self.pilot_password) < 14:
                    raise RuntimeError(
                        "A PILOT_PASSWORD of at least 14 characters is required for pilot_password auth"
                    )
            elif self.auth_mode != "magic_link":
                raise RuntimeError("AUTH_MODE must be magic_link or pilot_password")
            if self.agent_mail_enabled and self.agent_mail_provider == "capture":
                raise RuntimeError(
                    "Production agent mail requires AGENT_MAIL_PROVIDER=resend or ses"
                )
            if self.agent_mail_enabled and self.agent_mail_provider == "ses" and (
                not self.aws_access_key_id or not self.aws_secret_access_key
            ):
                raise RuntimeError(
                    "Dedicated AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required "
                    "for agent mail"
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()

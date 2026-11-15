"""Application settings loaded from environment variables."""
from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    session_ttl_seconds: int = max(60, int(os.getenv("SESSION_TTL_SECONDS", "3600")))
    session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "secure_session")
    session_cookie_secure: bool = _as_bool(os.getenv("SESSION_COOKIE_SECURE"), False)
    session_cookie_samesite: str = os.getenv("SESSION_COOKIE_SAMESITE", "lax").lower()


settings = Settings()

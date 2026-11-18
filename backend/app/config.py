"""Runtime configuration from env vars (see ../.env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BACKEND_DIR = Path(__file__).resolve().parent.parent
TZ = ZoneInfo("Asia/Kolkata")


def load_dotenv(path: Path = BACKEND_DIR / ".env") -> None:
    """Tiny .env loader (no dependency). Real env vars win. Inline '# comments' are stripped."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v not in (None, "") else default


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("SHIELD_DATA_DIR", str(BACKEND_DIR / "data"))))
    files_dir: Path = field(default_factory=lambda: Path(_env("SHIELD_FILES_DIR", str(BACKEND_DIR))))
    runtime_dir: Path = field(default_factory=lambda: Path(_env("SHIELD_RUNTIME_DIR", str(BACKEND_DIR / "runtime"))))
    mail_backend: str = field(default_factory=lambda: _env("SHIELD_MAIL", "fake"))
    gmail_token: Path = field(default_factory=lambda: Path(_env("GMAIL_TOKEN", str(BACKEND_DIR / "token.json"))))
    user_secret: str = field(default_factory=lambda: _env("SHIELD_USER_SECRET", "change-me"))
    founder_name: str = field(default_factory=lambda: _env("FOUNDER_NAME", "Sneha"))
    harness_model: str = field(default_factory=lambda: _env("SHIELD_HARNESS_MODEL", "claude-sonnet-5-5"))
    demo_today: str | None = field(default_factory=lambda: _env("SHIELD_TODAY", "2026-11-18"))
    review_base: str = field(default_factory=lambda: _env("SHIELD_REVIEW_BASE", "http://127.0.0.1:8000"))
    watch: str = field(default_factory=lambda: _env("SHIELD_WATCH", "fake"))  # off | fake | gmail
    watch_token: Path = field(default_factory=lambda: Path(_env("WATCH_GMAIL_TOKEN", str(BACKEND_DIR / "token_watch.json"))))
    enable_dev: bool = field(default_factory=lambda: _env("SHIELD_ENABLE_DEV", "1") == "1")
    verify_backoff: tuple[float, ...] = (1, 2, 4, 8, 15, 30, 60)

    def today(self) -> date:
        if self.demo_today:
            return date.fromisoformat(self.demo_today)
        return datetime.now(TZ).date()

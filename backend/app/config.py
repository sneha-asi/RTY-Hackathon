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
    data_dir: Path = field(default_factory=lambda: Path(_env("AXON_DATA_DIR", str(BACKEND_DIR / "data"))))
    files_dir: Path = field(default_factory=lambda: Path(_env("AXON_FILES_DIR", str(BACKEND_DIR))))
    mail_backend: str = field(default_factory=lambda: _env("AXON_MAIL", "fake"))
    gmail_token: Path = field(default_factory=lambda: Path(_env("GMAIL_TOKEN", str(BACKEND_DIR / "token.json"))))
    extractor: str = field(default_factory=lambda: _env("AXON_EXTRACTOR", "claude"))
    claude_model: str = field(default_factory=lambda: _env("AXON_CLAUDE_MODEL", "claude-sonnet-5-5"))
    claude_timeout_s: float = field(default_factory=lambda: float(_env("AXON_CLAUDE_TIMEOUT", "8")))
    demo_today: str | None = field(default_factory=lambda: _env("AXON_TODAY"))
    bolna_tool_token: str | None = field(default_factory=lambda: _env("BOLNA_TOOL_TOKEN"))
    bolna_api_key: str | None = field(default_factory=lambda: _env("BOLNA_API_KEY"))
    bolna_agent_id: str | None = field(default_factory=lambda: _env("BOLNA_AGENT_ID"))
    bolna_from_number: str | None = field(default_factory=lambda: _env("BOLNA_FROM_NUMBER"))
    enable_dev: bool = field(default_factory=lambda: _env("AXON_ENABLE_DEV", "1") == "1")

    def today(self) -> date:
        if self.demo_today:
            return date.fromisoformat(self.demo_today)
        return datetime.now(TZ).date()

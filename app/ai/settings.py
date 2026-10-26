"""AI settings, read from the environment (the project's .env is already loaded by app.config).

Kept separate from app.config.Settings on purpose: that class is constructed field-by-field in the tests, so adding
required fields to it would change every existing test. Nothing here is a secret default.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .. import config as _config                    # noqa: F401  (importing it loads .env)

BASE_DIR = Path(__file__).resolve().parents[2]


def _b(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    return default if raw is None or raw.strip() == "" else raw.strip().lower() in {"1", "true", "yes", "on"}


def _i(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _s(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).split("#")[0].strip()


def _p(name: str, default: str) -> Path:
    p = Path(_s(name, default))
    return p if p.is_absolute() else BASE_DIR / p


@dataclass(frozen=True)
class AiSettings:
    enabled: bool
    provider: str
    groq_api_key: str
    model_extract: str
    model_chat: str
    model_fast: str
    base_url: str
    timeout_s: int
    max_calls_per_minute: int
    max_input_tokens: int
    data_mode: str
    zdr_confirmed: bool
    outside_india_approved: bool
    embedding_model: str
    index_dir: Path
    library_dir: Path
    smtp_host: str
    smtp_port: int
    smtp_from: str
    smtp_sandbox: bool

    @classmethod
    def load(cls) -> "AiSettings":
        return cls(
            enabled=_b("AI_ENABLED"), provider=_s("AI_PROVIDER", "groq").lower(), groq_api_key=_s("GROQ_API_KEY"),
            model_extract=_s("AI_MODEL_EXTRACT", "openai/gpt-oss-120b"), model_chat=_s("AI_MODEL_CHAT", "openai/gpt-oss-120b"),
            model_fast=_s("AI_MODEL_FAST", "openai/gpt-oss-20b"), base_url=_s("AI_BASE_URL"),
            timeout_s=_i("AI_REQUEST_TIMEOUT_S", 60), max_calls_per_minute=_i("AI_MAX_CALLS_PER_MINUTE", 20),
            max_input_tokens=_i("AI_MAX_INPUT_TOKENS_PER_CALL", 3000), data_mode=_s("AI_DATA_MODE", "dummy").lower(),
            zdr_confirmed=_b("AI_ZDR_CONFIRMED"), outside_india_approved=_b("AI_OUTSIDE_INDIA_APPROVED"),
            embedding_model=_s("AI_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
            index_dir=_p("AI_INDEX_DIR", "data/ai_index"), library_dir=_p("AI_LIBRARY_DIR", "data/library"),
            smtp_host=_s("AI_SMTP_HOST", "localhost"), smtp_port=_i("AI_SMTP_PORT", 1025), smtp_from=_s("AI_SMTP_FROM"),
            smtp_sandbox=_b("AI_SMTP_SANDBOX", True))

    def status(self) -> dict:
        """What /api/ai/status reports. Never contains a secret."""
        reason = None
        if not self.enabled:
            reason = "AI is switched off (AI_ENABLED=false)."
        elif self.data_mode == "real" and not (self.zdr_confirmed and self.outside_india_approved):
            reason = ("Real data is blocked until Zero Data Retention and approval for processing outside India are "
                      "confirmed (AI_ZDR_CONFIRMED, AI_OUTSIDE_INDIA_APPROVED).")
        elif self.provider == "groq" and not self.groq_api_key:
            reason = "No Groq API key is configured."
        return {"enabled": reason is None, "provider": self.provider, "data_mode": self.data_mode,
                "models": {"extract": self.model_extract, "chat": self.model_chat, "fast": self.model_fast},
                "reason_if_disabled": reason}

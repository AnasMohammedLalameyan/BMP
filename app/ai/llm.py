"""The one place a model is called. Provider is chosen by settings (Groq by default, any OpenAI-compatible base URL as a
fallback). Every call is rate limited, retried politely, and logged WITHOUT its text (purpose, model, sizes, timing)."""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable, Type, TypeVar

from pydantic import BaseModel

from ..errors import ApiError
from .settings import AiSettings

log = logging.getLogger("bmp.ai")
T = TypeVar("T", bound=BaseModel)

_calls: deque = deque()
_lock = threading.Lock()

# Tests replace the model with this: runner(purpose, system, user, schema) -> schema instance. Never set in production.
_runner: Callable | None = None


def set_runner(fn: Callable | None) -> None:
    global _runner
    _runner = fn


def _model_name(s: AiSettings, purpose: str) -> str:
    return {"extract": s.model_extract, "fast": s.model_fast}.get(purpose, s.model_chat)


def _chat_model(s: AiSettings, purpose: str):
    name = _model_name(s, purpose)
    if s.provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=name, api_key=s.groq_api_key, temperature=0, timeout=s.timeout_s, max_retries=0)
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=name, base_url=s.base_url or None, api_key=s.groq_api_key or "none", temperature=0,
                      timeout=s.timeout_s, max_retries=0)


def _limit(s: AiSettings) -> None:
    """At most max_calls_per_minute calls a minute in this process; beyond that the caller gets a clear 429."""
    now = time.monotonic()
    with _lock:
        while _calls and now - _calls[0] > 60:
            _calls.popleft()
        if len(_calls) >= s.max_calls_per_minute:
            raise ApiError(429, "ai_rate_limited", "The AI assistant is busy. Please try again in a minute.")
        _calls.append(now)


def reset_limiter() -> None:
    with _lock:
        _calls.clear()


def invoke_structured(s: AiSettings, purpose: str, system: str, user: str, schema: Type[T], *,
                      meta: dict | None = None) -> T:
    """One model call with a strict output schema. `user` must already be masked. No tools are ever given."""
    started = time.monotonic()
    status = "ok"
    try:
        if _runner is not None:
            _limit(s)
            return _runner(purpose, system, user, schema)
        _limit(s)
        last = None
        base = None
        try:
            base = _chat_model(s, purpose)
        except Exception as e:                                               # noqa: BLE001
            log.warning("ai model could not be created purpose=%s error=%s", purpose, type(e).__name__)
            raise ApiError(503, "ai_unavailable", "AI is unavailable right now. You can continue by hand.")
        # JSON-schema output first (the model must answer in the schema); some models answer in prose when a tool call
        # is forced, so if the provider refuses the request, fall back once to JSON mode, then to function calling.
        for method in ("json_schema", "json_mode", "function_calling"):
            try:
                model = base.with_structured_output(schema, method=method)
            except Exception as e:                                           # noqa: BLE001
                last = e
                continue
            done = False
            for attempt in range(3):
                try:
                    extra = "\nReply with JSON only." if method == "json_mode" else ""
                    out = model.invoke([("system", system + extra), ("user", user)])
                    if isinstance(out, dict):
                        out = schema.model_validate(out)
                    return out
                except Exception as e:                                       # noqa: BLE001
                    last = e
                    if "rate" in type(e).__name__.lower() or getattr(e, "status_code", None) == 429:
                        wait = 2 ** attempt
                        try:
                            wait = float(e.response.headers.get("retry-after", wait))
                        except Exception:                                    # noqa: BLE001
                            pass
                        time.sleep(min(wait, 10))
                        continue
                    done = True                                              # a refused request: try the next method
                    break
            if not done:
                break                                                        # rate limited three times: stop
        status = "error"
        log.warning("ai call failed purpose=%s error=%s", purpose, type(last).__name__)
        raise ApiError(503, "ai_unavailable", "AI is unavailable right now. You can continue by hand.")
    except ApiError as e:
        status = e.code
        raise
    finally:
        log.info("ai call purpose=%s model=%s status=%s chars_in=%d ms=%.0f %s", purpose, _model_name(s, purpose),
                 status, len(system) + len(user), (time.monotonic() - started) * 1000,
                 " ".join(f"{k}={v}" for k, v in (meta or {}).items()))

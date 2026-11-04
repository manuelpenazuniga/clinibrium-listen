"""In-memory session registry + provider/access resolution (no DB, SPECS §2)."""
from __future__ import annotations

import hmac
import os
import uuid
from typing import Any

from api.demo_cases import load_demo_cases
from api.listen.session import Session
from api.muse.interfaces import MuseMode, Providers, get_providers

SESSIONS: dict[str, Session] = {}
MAX_SESSIONS = 200


def muse_mode(requested: str | None = None) -> MuseMode:
    mode = requested or os.environ.get("MUSE_MODE", "mock")
    if mode not in ("mock", "replay", "live"):
        raise ValueError(f"unknown mode {mode!r}")
    return mode  # type: ignore[return-value]


def live_audio_allowed(access_code: str | None) -> bool:
    """True only with `LIVE_AUDIO=1` AND a matching, non-empty DEMO_ACCESS_CODE."""
    if os.environ.get("LIVE_AUDIO") != "1":
        return False
    expected = os.environ.get("DEMO_ACCESS_CODE", "")
    if not expected or not access_code:
        return False
    return hmac.compare_digest(expected.encode(), access_code.encode())


def _demo_case(case_id: str) -> dict[str, Any]:
    for c in load_demo_cases():
        if c.get("id") == case_id:
            return c
    raise KeyError(case_id)


def build(mode: MuseMode, demo_case: str | None) -> Providers:
    if mode == "mock" and demo_case:
        from api.muse.mock import ScriptTurn, build_providers

        case = _demo_case(demo_case)
        script = [ScriptTurn(t["text"], t["start_ms"], t["end_ms"]) for t in case["turns"]]
        return build_providers(script=script)
    return get_providers(mode)


def create(mode: str | None = None, demo_case: str | None = None,
           access_code: str | None = None, session_id: str | None = None) -> Session:
    if len(SESSIONS) >= MAX_SESSIONS:
        oldest = next(iter(SESSIONS))
        SESSIONS.pop(oldest)
    sid = session_id or uuid.uuid4().hex[:12]
    s = Session(sid, build(muse_mode(mode), demo_case),
                live_audio_allowed=live_audio_allowed(access_code))
    SESSIONS[sid] = s
    return s


def get_or_create(session_id: str, access_code: str | None = None) -> Session:
    return SESSIONS.get(session_id) or create(session_id=session_id, access_code=access_code)


__all__ = ["SESSIONS", "create", "get_or_create", "live_audio_allowed", "muse_mode"]

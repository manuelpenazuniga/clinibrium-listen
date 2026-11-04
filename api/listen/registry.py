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


class LiveNotAllowed(PermissionError):
    """Live mode was requested without LIVE_AUDIO=1 + a valid DEMO_ACCESS_CODE."""


def resolve_mode(requested: str | None, access_ok: bool) -> MuseMode:
    """Server-side gate for live Meta usage (SPECS §7 ws/routes, §9).

    - `live` only with `access_ok` (LIVE_AUDIO=1 AND a valid DEMO_ACCESS_CODE);
      explicitly asking for it without access is refused, never granted.
    - No explicit mode → MUSE_MODE, except that on a `MUSE_MODE=live` server a
      client without access gets `replay` (the public never spends credits).
    """
    if requested is not None:
        mode = muse_mode(requested)
        if mode == "live" and not access_ok:
            raise LiveNotAllowed("live mode requires LIVE_AUDIO=1 and a valid access code")
        return mode
    default = muse_mode()
    return "replay" if default == "live" and not access_ok else default


def create(mode: str | None = None, demo_case: str | None = None,
           access_code: str | None = None, session_id: str | None = None) -> Session:
    access_ok = live_audio_allowed(access_code)
    resolved = resolve_mode(mode, access_ok)
    if resolved == "live":
        from api.muse.daily_cap import daily_cap

        daily_cap().charge("sessions")  # DailyCapExceeded → refused before any call
    while len(SESSIONS) >= MAX_SESSIONS:
        evict(next(iter(SESSIONS)))
    sid = session_id or uuid.uuid4().hex[:12]
    s = Session(sid, build(resolved, demo_case), live_audio_allowed=access_ok)
    SESSIONS[sid] = s
    return s


def evict(session_id: str) -> None:
    """Drop a session AND cancel its background tasks (worker, model lane,
    finalize pass), so an evicted session never keeps calling models."""
    s = SESSIONS.pop(session_id, None)
    if s is not None:
        s.cancel_tasks()


def get_or_create(session_id: str, access_code: str | None = None) -> Session:
    return SESSIONS.get(session_id) or create(session_id=session_id, access_code=access_code)


__all__ = ["SESSIONS", "LiveNotAllowed", "create", "evict", "get_or_create",
           "live_audio_allowed", "muse_mode", "resolve_mode"]

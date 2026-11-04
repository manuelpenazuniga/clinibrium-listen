"""Window clock (SPECS §7 onset.py). Pure.

`context.last_known_well_minutes_ago` + the wall-clock time of the turn that
stated it → absolute last-known-well time. Windows come from
`config/protocol.json` (configure per local stroke protocol). Visible only
when a red flag is shown or a confirmation is pending. No treatment text.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from api.catalog import load_config
from api.listen.contracts import (
    ConfirmationRequest,
    EngineResultView,
    FieldState,
    OnsetInfo,
    Turn,
    WindowView,
)

LKW_KEY = "context.last_known_well_minutes_ago"


def compute_onset(fields: Mapping[str, FieldState], turns: Sequence[Turn],
                  result: EngineResultView | None,
                  confirmations: Sequence[ConfirmationRequest],
                  started_at: datetime, now: datetime) -> OnsetInfo | None:
    visible = bool(result and result.red_flags) or any(
        c.status == "pending" for c in confirmations)
    fs = fields.get(LKW_KEY)
    if not visible or fs is None or fs.status == "rejected" or not isinstance(fs.value, int):
        return None
    ev = next((e for e in reversed(fs.evidence) if e.turn_id is not None), None)
    turn = next((t for t in turns if ev and t.turn_id == ev.turn_id), None)
    stated_at = started_at + timedelta(milliseconds=turn.end_ms if turn else 0)
    lkw = stated_at - timedelta(minutes=fs.value)
    elapsed = max(0, int((now - lkw).total_seconds() // 60))
    windows = [
        WindowView(label_es=w["label_es"], label_en=w["label_en"], minutes=int(w["minutes"]),
                   elapsed_min=elapsed, remaining_min=max(0, int(w["minutes"]) - elapsed))
        for w in load_config("protocol.json")["windows"]
    ]
    quote = next((e.quote for e in reversed(fs.evidence) if e.quote), None)
    return OnsetInfo(last_known_well_at=lkw.isoformat(timespec="seconds"), quote=quote,
                     windows=windows)


__all__ = ["LKW_KEY", "compute_onset"]

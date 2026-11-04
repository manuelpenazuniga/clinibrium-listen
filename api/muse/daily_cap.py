"""Server-side DAILY caps on live Meta usage (deploy guard).

A leaked DEMO_ACCESS_CODE must not be able to drain credits, so every live
resource is counted per UTC day, process-wide, and refused once its cap is hit:

    LIVE_DAILY_SESSIONS     live sessions created per day        (default 20)
    LIVE_DAILY_MODEL_CALLS  live LLM requests per day            (default 300)
    LIVE_DAILY_ASR_STREAMS  realtime + push-to-talk ASR per day  (default 40)

`0` disables that resource. Counts persist to `LIVE_CAP_FILE` (default:
a file in the system temp dir) so a restart does not reset them. These sit on
top of the per-process, fail-closed budget guards of 1B1/1B2
(MUSE_MAX_LIVE_CALLS, MUSE_MAX_WONDER_CALLS, MUSE_MAX_AUDIO_SECONDS).
No transcript, key or payload is ever written; only counters.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, int] = {"sessions": 20, "model_calls": 300, "asr_streams": 40}
ENV: dict[str, str] = {"sessions": "LIVE_DAILY_SESSIONS",
                       "model_calls": "LIVE_DAILY_MODEL_CALLS",
                       "asr_streams": "LIVE_DAILY_ASR_STREAMS"}


class DailyCapExceeded(RuntimeError):
    """A live resource hit its daily cap; refuse (fail closed)."""


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


class DailyCap:
    def __init__(self, path: Path | None = None, today: Callable[[], str] = _today) -> None:
        env = os.environ.get("LIVE_CAP_FILE", "").strip()
        self.path = path or (Path(env) if env else
                             Path(tempfile.gettempdir()) / "clinibrium-live-cap.json")
        self._today = today
        self._lock = threading.Lock()

    def limit(self, resource: str) -> int:
        raw = os.environ.get(ENV[resource], "").strip()
        try:
            return max(0, int(raw)) if raw else DEFAULTS[resource]
        except ValueError:
            return 0  # unparsable → disabled (fail closed)

    def _load(self) -> dict[str, Any]:
        try:
            data: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if data.get("day") != self._today():
            data = {"day": self._today(), "counts": {}}
        return data

    def used(self, resource: str) -> int:
        with self._lock:
            return int(self._load()["counts"].get(resource, 0))

    def charge(self, resource: str, n: int = 1) -> None:
        """Count `n` uses of `resource` today, or raise before anything is spent."""
        with self._lock:
            limit = self.limit(resource)
            data = self._load()
            used = int(data["counts"].get(resource, 0))
            if used + n > limit:
                raise DailyCapExceeded(
                    f"daily cap reached for live {resource} ({limit}/day); try tomorrow")
            data["counts"][resource] = used + n
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(data), encoding="utf-8")
            except OSError:
                pass  # the in-process check above still held for this call


_CAP: DailyCap | None = None


def daily_cap() -> DailyCap:
    global _CAP
    if _CAP is None:
        _CAP = DailyCap()
    return _CAP


def reset_for_tests(cap: DailyCap | None = None) -> None:
    global _CAP
    _CAP = cap


__all__ = ["DailyCap", "DailyCapExceeded", "daily_cap", "reset_for_tests"]

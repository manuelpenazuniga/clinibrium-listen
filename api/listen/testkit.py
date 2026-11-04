"""Helpers shared by the Listen tests and the bench (mock providers only, no network)."""
from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from api.listen import policy
from api.listen.contracts import Evidence, ExtractorOut, FieldState, FieldValue
from api.listen.evidence import validate_delta
from api.listen.session import Session
from api.muse.interfaces import ExtractCtx, Providers
from api.muse.mock import MockExtractor, build_providers, extract_text

T0 = datetime(2026, 11, 4, 15, 0, 0, tzinfo=UTC)


class FixedClock:
    """Deterministic clock: advances `step_ms` per call."""

    def __init__(self, start: datetime = T0, step_ms: int = 0) -> None:
        self.now = start
        self.step = timedelta(milliseconds=step_ms)

    def __call__(self) -> datetime:
        t = self.now
        self.now = t + self.step
        return t


class GateExtractor:
    """Mock extractor that blocks until `gate` is set (stale-epoch tests)."""

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.calls: list[ExtractCtx] = []

    async def extract(self, ctx: ExtractCtx) -> ExtractorOut:
        self.calls.append(ctx)
        await self.gate.wait()
        return await MockExtractor().extract(ctx)


class SpyExtractor:
    def __init__(self) -> None:
        self.calls: list[ExtractCtx] = []

    async def extract(self, ctx: ExtractCtx) -> ExtractorOut:
        self.calls.append(ctx)
        return await MockExtractor().extract(ctx)


def providers(**overrides: Any) -> Providers:
    return dataclasses.replace(build_providers(), **overrides)


def new_session(session_id: str = "test", *, clock: FixedClock | None = None,
                **overrides: Any) -> Session:
    return Session(session_id, providers(**overrides), clock=clock or FixedClock())


async def dictate(s: Session, texts: Iterable[str]) -> None:
    for t in texts:
        await s.text_turn(t)
        await s.drain()


async def send(s: Session, msg: dict[str, Any]) -> None:
    await s.client(msg)
    await s.drain()


def proposed_fields(texts: list[str], status: str = "proposed") -> dict[str, FieldState]:
    """Merge mock-extracted, evidence-validated values from `texts` (pure)."""
    fields: dict[str, FieldState] = {}
    for n, t in enumerate(texts, 1):
        for d in extract_text(t):
            acc = validate_delta(d, texts)
            assert not isinstance(acc, str), acc
            ev = Evidence(source="dictated", quote=acc.quote, turn_id=n, start_ms=0,
                          document_id=None, confidence_pct=90)
            policy.merge(fields, policy.new_field(acc.key, acc.value, ev))
    if status == "confirmed":
        for fs in fields.values():
            fs.status = "confirmed"
            fs.sticky_alert = False
    return fields


def field(key: str, value: FieldValue, status: str = "proposed") -> FieldState:
    ev = Evidence(source="manual" if status == "confirmed" else "dictated", quote=None,
                  turn_id=None, start_ms=None, document_id=None, confidence_pct=100)
    return FieldState(key=key, value=value, status=status,  # type: ignore[arg-type]
                      evidence=[ev], sticky_alert=False, conflict=None)


__all__ = ["T0", "FixedClock", "GateExtractor", "SpyExtractor", "dictate", "field",
           "new_session", "proposed_fields", "providers", "send"]

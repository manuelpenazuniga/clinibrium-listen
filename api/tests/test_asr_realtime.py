"""RealtimeAsrStream against a local fake Meta websocket server (no external network)."""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from websockets.asyncio.server import ServerConnection, serve

from api.muse import asr_realtime as rt
from api.muse.asr_realtime import (
    BudgetExceeded,
    LiveDisabled,
    LiveStopped,
    RealtimeAsrStream,
    UsageLedger,
)
from api.muse.interfaces import AsrEvent, AsrStream

KEY = "test-key-not-real"
SECOND = b"\x01\x00" * 16_000  # 1 s of PCM16 mono 16 kHz
FRAME = SECOND[:3200]  # 100 ms


def _turn_script(tid: str, words: list[str], complete_first: bool = False) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"type": "speechStart", "turnId": tid}]
    for k in range(1, len(words) + 1):
        out.append({"type": "transcript", "transcript": " ".join(words[:k]), "final": False})
    done = [{"type": "speechEnd", "turnId": tid},
            {"type": "speechComplete", "turnId": tid, "transcript": " ".join(words) + "."}]
    return out + (done[::-1] if complete_first else done)


@dataclass
class Conn:
    """What one fake connection does: script emitted after `after_bytes`, then `close_code`."""

    script: list[dict[str, Any]] = field(default_factory=list)
    after_bytes: int = 1
    close_code: int | None = None  # close right after the script (None: wait for endStream)
    send_handshake: bool = True


@dataclass
class FakeMeta:
    conns: list[Conn]
    configs: list[dict[str, Any]] = field(default_factory=list)
    bytes_rx: list[int] = field(default_factory=list)
    end_streams: int = 0

    async def handler(self, ws: ServerConnection) -> None:
        idx = len(self.configs)
        spec = self.conns[min(idx, len(self.conns) - 1)]
        self.configs.append(json.loads(await ws.recv()))
        self.bytes_rx.append(0)
        if spec.send_handshake:
            await ws.send(json.dumps({"sessionId": f"sess-{idx}"}))
        sent = False
        async for msg in ws:
            if isinstance(msg, bytes):
                self.bytes_rx[idx] += len(msg)
                if not sent and self.bytes_rx[idx] >= spec.after_bytes:
                    sent = True
                    for ev in spec.script:
                        await ws.send(json.dumps(ev))
                    if spec.close_code is not None:
                        await ws.close(spec.close_code, "fake")
                        return
            elif json.loads(msg).get("type") == "endStream":
                self.end_streams += 1
                await ws.send(json.dumps({"type": "transcript", "transcript": "", "final": True}))
                await ws.close(1000)
                return


Factory = Callable[..., Awaitable[tuple[RealtimeAsrStream, FakeMeta]]]


@pytest.fixture
def ledger(tmp_path: Path) -> UsageLedger:
    return UsageLedger(path=tmp_path / "usage.jsonl", max_audio_seconds=60)


@pytest.fixture
async def fake() -> AsyncIterator[Factory]:
    servers: list[Any] = []

    async def make(conns: list[Conn], ledger: UsageLedger,
                   **kw: Any) -> tuple[RealtimeAsrStream, FakeMeta]:
        meta = FakeMeta(conns)
        server = await serve(meta.handler, "127.0.0.1", 0)
        servers.append(server)
        port = next(iter(server.sockets)).getsockname()[1]
        kw.setdefault("pace", False)
        stream = RealtimeAsrStream(KEY, url=f"ws://127.0.0.1:{port}", ledger=ledger,
                                   keywords=["vértigo", "diplopía"], **kw)
        return stream, meta

    yield make
    for s in servers:
        s.close()
        await s.wait_closed()


async def _collect(stream: RealtimeAsrStream, frames: int = 5) -> list[AsrEvent]:
    events: list[AsrEvent] = []

    async def consume() -> None:
        async for ev in stream.events():
            events.append(ev)

    task = asyncio.create_task(consume())
    for _ in range(frames):
        await stream.feed(FRAME)
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.1)
    await stream.close()
    await asyncio.wait_for(task, 5)
    return events


def _kinds(events: list[AsrEvent]) -> list[str]:
    return [e.kind for e in events]


# ------------------------------------------------------------------ protocol


def test_is_an_asr_stream(ledger: UsageLedger) -> None:
    assert isinstance(RealtimeAsrStream(KEY, ledger=ledger), AsrStream)


def test_config_frame_shape() -> None:
    f = rt.config_frame("abc", ["vértigo"], ["Spanish"])
    assert f["authorization"] == {"accessToken": "Bearer abc"}
    assert f["model"] == "muse-voice-transcribe-1.0"
    assert f["audioEncoding"] == "PCM_16KHZ"
    assert f["mode"] == "ENDPOINTING" and f["partialMode"] == "CUMULATIVE"
    assert f["languageBias"] == ["Spanish"] and f["keywords"] == ["vértigo"]
    assert rt.config_frame("Bearer abc", [], [])["authorization"]["accessToken"] == "Bearer abc"


def test_keywords_load_from_config() -> None:
    kws = rt.load_keywords()
    assert "vértigo" in kws and "diplopía" in kws


async def test_first_frame_is_config_and_audio_is_binary(fake: Factory,
                                                        ledger: UsageLedger) -> None:
    stream, meta = await fake([Conn()], ledger)
    await _collect(stream, frames=3)
    cfg = meta.configs[0]
    assert cfg["authorization"]["accessToken"] == f"Bearer {KEY}"
    assert cfg["keywords"] == ["vértigo", "diplopía"]
    assert meta.bytes_rx == [3 * len(FRAME)]
    assert meta.end_streams == 1  # endStream sent on close
    assert stream.session_ids == ["sess-0"]


async def test_events_map_to_asr_events(fake: Factory, ledger: UsageLedger) -> None:
    script = _turn_script("a", ["paciente", "de", "68"]) + _turn_script(
        "b", ["sin", "diplopía"], complete_first=True)
    stream, _ = await fake([Conn(script=script)], ledger, first_turn_id=7)
    ev = await _collect(stream)
    assert _kinds(ev) == ["speech_start", "partial", "partial", "partial", "final", "speech_end",
                          "speech_start", "partial", "partial", "final", "speech_end"]
    assert [e.text for e in ev if e.kind == "partial"][:3] == [
        "paciente", "paciente de", "paciente de 68"]
    finals = [e for e in ev if e.kind == "final"]
    assert [(f.turn_id, f.text) for f in finals] == [(7, "paciente de 68."), (8, "sin diplopía.")]
    assert all(f.start_ms is not None and f.end_ms is not None for f in finals)
    assert all(e.turn_id in (7, 8) for e in ev)


async def test_explicit_ms_fields_are_used(fake: Factory, ledger: UsageLedger) -> None:
    script = [{"type": "speechStart", "turnId": 1, "startMs": 120},
              {"type": "speechEnd", "turnId": 1, "endMs": 980},
              {"type": "speechComplete", "turnId": 1, "transcript": "hola"}]
    stream, _ = await fake([Conn(script=script)], ledger)
    ev = await _collect(stream)
    final = next(e for e in ev if e.kind == "final")
    assert (final.start_ms, final.end_ms, final.text) == (120, 980, "hola")


async def test_audio_progress_drives_timestamps(fake: Factory, ledger: UsageLedger) -> None:
    script = [{"type": "audioProgress", "audioProcessedMs": 300},
              {"type": "speechStart", "turnId": 1},
              {"type": "audioProgress", "audioProcessedMs": 900},
              {"type": "speechEnd", "turnId": 1},
              {"type": "speechComplete", "turnId": 1, "transcript": "hola"}]
    stream, _ = await fake([Conn(script=script)], ledger)
    ev = await _collect(stream)
    final = next(e for e in ev if e.kind == "final")
    assert (final.start_ms, final.end_ms) == (300, 900)


async def test_unfinished_turn_is_flushed_on_close(fake: Factory, ledger: UsageLedger) -> None:
    script = [{"type": "speechStart", "turnId": 1},
              {"type": "transcript", "transcript": "vértigo continuo"}]
    stream, _ = await fake([Conn(script=script)], ledger)
    ev = await _collect(stream)
    assert _kinds(ev) == ["speech_start", "partial", "final", "speech_end"]
    assert ev[2].text == "vértigo continuo"


async def test_server_error_event(fake: Factory, ledger: UsageLedger) -> None:
    stream, _ = await fake([Conn(script=[{"type": "error", "code": "BAD_AUDIO"}])], ledger)
    ev = await _collect(stream)
    assert [e.error_code for e in ev if e.kind == "error"] == ["BAD_AUDIO"]


async def test_quota_error_event_stops_live(fake: Factory, ledger: UsageLedger) -> None:
    stream, _ = await fake([Conn(script=[{"type": "error", "code": "QUOTA_EXCEEDED"}])], ledger)
    await _collect(stream)
    with pytest.raises(LiveStopped):
        ledger.check_live()


# ---------------------------------------------------------------- resilience


async def test_one_reconnect_after_1013(fake: Factory, ledger: UsageLedger) -> None:
    conns = [Conn(script=[{"type": "speechStart", "turnId": "x"}], close_code=1013),
             Conn(script=_turn_script("x", ["mareo"]), after_bytes=1)]
    stream, meta = await fake(conns, ledger)
    ev = await _collect(stream, frames=8)
    assert len(meta.configs) == 2 and stream.connections == 2
    # the dropped turn is closed, the new one gets the next id
    assert _kinds(ev) == ["speech_start", "speech_end", "speech_start", "partial", "final",
                          "speech_end"]
    assert [e.turn_id for e in ev] == [1, 1, 2, 2, 2, 2]
    assert not [e for e in ev if e.kind == "error"]


async def test_1013_twice_stops_live(fake: Factory, ledger: UsageLedger) -> None:
    stream, meta = await fake([Conn(close_code=1013)], ledger)
    ev = await _collect(stream, frames=6)
    assert len(meta.configs) == 2  # exactly one reconnect, then stop
    assert [e.error_code for e in ev if e.kind == "error"] == ["1013_repeated"]
    with pytest.raises(LiveStopped):
        await RealtimeAsrStream(KEY, ledger=ledger).feed(FRAME)


async def test_at_most_one_reconnect(fake: Factory, ledger: UsageLedger) -> None:
    stream, meta = await fake([Conn(close_code=1011)], ledger)
    ev = await _collect(stream, frames=6)
    assert len(meta.configs) == 2
    assert [e.error_code for e in ev if e.kind == "error"] == ["close_1011"]


async def test_policy_close_is_not_retried(fake: Factory, ledger: UsageLedger) -> None:
    stream, meta = await fake([Conn(close_code=1008)], ledger)
    ev = await _collect(stream, frames=4)
    assert len(meta.configs) == 1
    assert [e.error_code for e in ev if e.kind == "error"] == ["close_1008"]


async def test_feed_after_failure_is_ignored(fake: Factory, ledger: UsageLedger) -> None:
    stream, _ = await fake([Conn(close_code=1008)], ledger)
    await _collect(stream, frames=2)
    await stream.feed(FRAME)  # no raise, no hang


async def test_pacing_never_runs_ahead(fake: Factory, ledger: UsageLedger,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rt, "MAX_AHEAD_S", 0.2)
    stream, meta = await fake([Conn()], ledger, pace=True)
    t0 = time.monotonic()
    events = asyncio.create_task(_drain(stream))
    await stream.feed(SECOND)  # 1 s burst
    await stream.close()
    await events
    assert meta.bytes_rx == [len(SECOND)]
    assert time.monotonic() - t0 >= 0.7  # ≈ 1 s audio − 0.2 s lead − one frame


async def _drain(stream: RealtimeAsrStream) -> None:
    async for _ in stream.events():
        pass


# -------------------------------------------------------------------- budget


async def test_live_disabled_without_cap(tmp_path: Path, fake: Factory) -> None:
    ledger = UsageLedger(path=tmp_path / "u.jsonl", max_audio_seconds=0)
    stream, meta = await fake([Conn()], ledger)
    with pytest.raises(LiveDisabled):
        await stream.feed(FRAME)
    await stream.close()
    assert meta.configs == [] and not (tmp_path / "u.jsonl").exists()


def test_from_env_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MUSE_USAGE_LOG", str(tmp_path / "u.jsonl"))
    for raw in ("", "0", "abc"):
        monkeypatch.setenv("MUSE_MAX_AUDIO_SECONDS", raw)
        with pytest.raises(LiveDisabled):
            UsageLedger.from_env().check_live()
    monkeypatch.setenv("MUSE_MAX_AUDIO_SECONDS", "900")
    UsageLedger.from_env().check_live()


async def test_audio_cap_enforced_before_send(tmp_path: Path, fake: Factory) -> None:
    ledger = UsageLedger(path=tmp_path / "u.jsonl", max_audio_seconds=0.25)
    stream, meta = await fake([Conn()], ledger)
    task = asyncio.create_task(_drain_kinds(stream))
    await stream.feed(FRAME)
    await stream.feed(FRAME)
    await stream.feed(FRAME)  # over the cap mid-stream: error event, stream ends
    await stream.feed(FRAME)  # ignored
    await stream.close()
    assert "BudgetExceeded" in await asyncio.wait_for(task, 5)
    assert sum(meta.bytes_rx) == 2 * len(FRAME)
    with pytest.raises(BudgetExceeded):  # a fresh stream is refused before connecting
        await RealtimeAsrStream(KEY, ledger=ledger).feed(FRAME)


async def _drain_kinds(stream: RealtimeAsrStream) -> list[str]:
    return [e.error_code or e.kind async for e in stream.events()]


async def test_connection_cap(tmp_path: Path, fake: Factory) -> None:
    ledger = UsageLedger(path=tmp_path / "u.jsonl", max_audio_seconds=60, max_connections=1)
    s1, _ = await fake([Conn()], ledger)
    await _collect(s1, frames=1)
    s2, meta2 = await fake([Conn()], ledger)
    ev = await _collect(s2, frames=1)
    assert meta2.configs == []
    assert [e.error_code for e in ev if e.kind == "error"] == ["BudgetExceeded"]


async def test_usage_log_rows_and_cross_run_totals(fake: Factory, ledger: UsageLedger) -> None:
    script = _turn_script("a", ["sin", "diplopía"])
    stream, _ = await fake([Conn(script=script)], ledger, purpose="unit")
    await _collect(stream, frames=5)
    raw = ledger.path.read_text()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert [r["status"] for r in rows] == ["open", "closed"]
    for r in rows:
        assert set(r) == {"ts", "endpoint", "model", "audio_seconds", "purpose", "status"}
        assert r["endpoint"] == "realtime" and r["purpose"] == "unit"
    assert rows[1]["audio_seconds"] == pytest.approx(0.5)
    assert KEY not in raw and "diplop" not in raw  # no keys, no transcripts
    again = UsageLedger(path=ledger.path, max_audio_seconds=60)
    assert again.audio_seconds == pytest.approx(0.5) and again.connections == 1


async def test_close_without_audio_opens_nothing(fake: Factory, ledger: UsageLedger) -> None:
    stream, meta = await fake([Conn()], ledger)
    task = asyncio.create_task(_drain(stream))
    await stream.close()
    await asyncio.wait_for(task, 2)
    assert meta.configs == [] and not ledger.path.exists()

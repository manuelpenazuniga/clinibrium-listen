"""FileAsr (push-to-talk) against an httpx MockTransport (no network)."""
from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import httpx
import pytest

from api.muse.asr_file import FileAsr, InvalidWav, parse_response, wav_seconds
from api.muse.asr_realtime import (
    BudgetExceeded,
    LiveAsrError,
    LiveDisabled,
    LiveStopped,
    UsageLedger,
)
from api.muse.interfaces import AsrFile

KEY = "test-key-not-real"


def make_wav(seconds: float = 2.0, rate: int = 16_000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate) * channels)
    return buf.getvalue()


@pytest.fixture
def ledger(tmp_path: Path) -> UsageLedger:
    return UsageLedger(path=tmp_path / "usage.jsonl", max_audio_seconds=60)


def _asr(ledger: UsageLedger, handler: object) -> FileAsr:
    return FileAsr(KEY, ledger=ledger, keywords=["vértigo"], backoff_s=0,
                   base_url="https://example.invalid/v1",
                   transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


def test_is_an_asr_file(ledger: UsageLedger) -> None:
    assert isinstance(FileAsr(KEY, ledger=ledger), AsrFile)


async def test_request_shape_and_transcript_fallback(ledger: UsageLedger) -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"sessionId": "s", "transcript": " sin diplopía. ",
                                         "audioDurationMs": 2000, "turns": []})

    turns = await _asr(ledger, handler).transcribe(make_wav(), first_turn_id=4)
    assert [(t.turn_id, t.start_ms, t.end_ms, t.text) for t in turns] == [
        (4, 0, 2000, "sin diplopía.")]
    req = seen[0]
    assert req.url.path == "/v1/asr/transcribe"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    body = req.content.decode("utf-8", errors="replace")
    assert 'name="audio"' in body and 'name="request"' in body
    part = body.split('name="request"', 1)[1].split("\r\n\r\n", 1)[1].split("\r\n--", 1)[0]
    assert json.loads(part) == {"model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV",
                                "languageBias": ["Spanish"], "keywords": ["vértigo"]}


def test_parse_turns() -> None:
    data = {"transcript": "a b", "audioDurationMs": 5000, "turns": [
        {"startMs": 0, "endMs": 1500, "transcript": "Paciente de 68 años."},
        {"startMs": 1600, "endMs": 4000, "transcript": "  "},
        {"startMs": 4100, "endMs": 5000, "transcript": "Sin diplopía."}]}
    turns = parse_response(data, first_turn_id=1)
    assert [(t.turn_id, t.start_ms, t.end_ms, t.text) for t in turns] == [
        (1, 0, 1500, "Paciente de 68 años."), (2, 4100, 5000, "Sin diplopía.")]
    assert parse_response({"transcript": "", "turns": []}, 1) == []


async def test_retries_5xx_at_most_three_times(ledger: UsageLedger) -> None:
    calls = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    with pytest.raises(LiveAsrError):
        await _asr(ledger, handler).transcribe(make_wav(1.0), 1)
    assert calls == 4  # 1 try + 3 retries
    rows = [json.loads(x) for x in ledger.path.read_text().splitlines()]
    assert [r["status"] for r in rows] == ["http_503"] * 4
    assert ledger.audio_seconds == pytest.approx(4.0)


async def test_retry_then_success(ledger: UsageLedger) -> None:
    calls = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"transcript": "mareo", "audioDurationMs": 1000})

    turns = await _asr(ledger, handler).transcribe(make_wav(1.0), 1)
    assert [t.text for t in turns] == ["mareo"] and calls == 2


@pytest.mark.parametrize("status", [402, 429])
async def test_quota_status_stops_live(ledger: UsageLedger, status: int) -> None:
    calls = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    asr = _asr(ledger, handler)
    with pytest.raises(LiveStopped):
        await asr.transcribe(make_wav(1.0), 1)
    assert calls == 1
    with pytest.raises(LiveStopped):
        await asr.transcribe(make_wav(1.0), 1)
    assert calls == 1


async def test_4xx_not_retried(ledger: UsageLedger) -> None:
    calls = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": "bad"})

    with pytest.raises(LiveAsrError):
        await _asr(ledger, handler).transcribe(make_wav(1.0), 1)
    assert calls == 1


async def test_budget_fail_closed(tmp_path: Path) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError("must not be called")

    off = UsageLedger(path=tmp_path / "a.jsonl", max_audio_seconds=0)
    with pytest.raises(LiveDisabled):
        await _asr(off, handler).transcribe(make_wav(1.0), 1)
    small = UsageLedger(path=tmp_path / "b.jsonl", max_audio_seconds=1.5)
    with pytest.raises(BudgetExceeded):
        await _asr(small, handler).transcribe(make_wav(2.0), 1)
    assert not (tmp_path / "a.jsonl").exists() and not (tmp_path / "b.jsonl").exists()


@pytest.mark.parametrize("wav", [make_wav(1, rate=8000), make_wav(1, channels=2), b"nope"])
def test_invalid_wav(wav: bytes) -> None:
    with pytest.raises(InvalidWav):
        wav_seconds(wav)


def test_wav_seconds() -> None:
    assert wav_seconds(make_wav(2.5)) == pytest.approx(2.5)
    assert wav_seconds(make_wav(1, rate=24_000)) == pytest.approx(1.0)

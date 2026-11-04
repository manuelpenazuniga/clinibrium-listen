"""Opt-in live ASR test. Skipped unless MODEL_API_KEY and MUSE_LIVE_TESTS=1 are both set
(and MUSE_MAX_AUDIO_SECONDS > 0, enforced by the budget guard). CI never runs it.

Needs a scripted Spanish clip (≤ 10 s, mono 16-bit 16 kHz) at fixtures/audio/*.wav or
MUSE_LIVE_WAV=/path/clip.wav.
"""
from __future__ import annotations

import asyncio
import io
import os
import time
import wave
from pathlib import Path

import pytest

from api.muse.asr_file import FileAsr
from api.muse.asr_realtime import BYTES_PER_SECOND, CHUNK_BYTES, RealtimeAsrStream

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not (os.environ.get("MODEL_API_KEY") and os.environ.get("MUSE_LIVE_TESTS") == "1"),
    reason="live ASR test: set MODEL_API_KEY and MUSE_LIVE_TESTS=1",
)


def _clip() -> bytes:
    env = os.environ.get("MUSE_LIVE_WAV")
    paths = [Path(env)] if env else sorted((ROOT / "fixtures" / "audio").glob("*.wav"))
    if not paths:
        pytest.skip("no Spanish clip in fixtures/audio/ (or MUSE_LIVE_WAV)")
    return paths[0].read_bytes()


def _pcm(wav: bytes, max_s: float = 10.0) -> bytes:
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getframerate() == 16_000 and w.getnchannels() == 1
        return w.readframes(min(w.getnframes(), int(max_s * 16_000)))


async def test_live_realtime_partials_under_1s() -> None:
    pcm = _pcm(_clip())
    stream = RealtimeAsrStream(purpose="live_test")
    t0 = time.monotonic()
    kinds: list[str] = []
    finals: list[str] = []
    first_partial: float | None = None
    first_start: float | None = None

    async def consume() -> None:
        nonlocal first_partial, first_start
        async for ev in stream.events():
            kinds.append(ev.kind)
            now = time.monotonic() - t0
            if ev.kind == "speech_start" and first_start is None:
                first_start = now
            if ev.kind == "partial" and first_partial is None:
                first_partial = now
            if ev.kind == "final":
                finals.append(ev.text)

    task = asyncio.create_task(consume())
    frames = [pcm[i : i + CHUNK_BYTES] for i in range(0, len(pcm), CHUNK_BYTES)]
    for f in frames + [b"\x00" * CHUNK_BYTES] * 15:
        await stream.feed(f)
        await asyncio.sleep(len(f) / BYTES_PER_SECOND)
    await stream.close()
    await asyncio.wait_for(task, 15)
    assert "error" not in kinds, kinds
    assert finals and any(finals)
    assert first_partial is not None and first_start is not None
    assert first_partial - first_start < 1.0


async def test_live_file_transcribe() -> None:
    turns = await FileAsr(purpose="live_test").transcribe(_clip(), first_turn_id=1)
    assert turns and turns[0].text

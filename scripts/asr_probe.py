"""Stream a local Spanish WAV through the live realtime ASR relay; print events + latency.

Manual verification only (never run in CI). Respects the 1B1 budget guard:
MUSE_MAX_AUDIO_SECONDS must be set (> 0) and every connection / second of audio is
appended to fixtures/usage/1B1.jsonl. Clips are capped at 10 s by default.

  MUSE_MAX_AUDIO_SECONDS=900 uv run python scripts/asr_probe.py --wav fixtures/audio/clip.wav
  uv run python scripts/asr_probe.py --wav clip.wav --file      # push-to-talk endpoint instead

Make a clip on macOS:
  say -v Paulina -o /tmp/c.aiff "Paciente de 68 años, vértigo continuo hace 12 horas."
  afconvert -f WAVE -d LEI16@16000 -c 1 /tmp/c.aiff fixtures/audio/clip.wav

Latency columns:
  t_s       wall seconds since the first audio frame was sent (≈ audio position, real-time pacing)
  lag_ms    for partials: t − end of the audio the server reports as processed (audioProgress);
            (null when the server sends no audioProgress).
The transcript text is printed to the terminal only; nothing is written to disk but usage rows.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "engine")]

from api.muse.asr_file import FileAsr, wav_seconds  # noqa: E402
from api.muse.asr_realtime import (  # noqa: E402
    BYTES_PER_SECOND,
    CHUNK_BYTES,
    LiveAsrError,
    RealtimeAsrStream,
    default_ledger,
)


def read_pcm(path: Path, max_seconds: float) -> bytes:
    data = path.read_bytes()
    seconds = wav_seconds(data)  # validates mono 16-bit 16/24 kHz
    with wave.open(io.BytesIO(data)) as w:
        if w.getframerate() != 16_000:
            sys.exit("realtime probe needs a 16 kHz WAV")
        pcm = w.readframes(w.getnframes())
    if seconds > max_seconds:
        print(f"clip is {seconds:.1f} s; truncating to {max_seconds:.1f} s", file=sys.stderr)
        pcm = pcm[: int(max_seconds * BYTES_PER_SECOND) // 2 * 2]
    return pcm


async def probe_realtime(pcm: bytes, tail_silence_s: float) -> dict[str, object]:
    stream = RealtimeAsrStream(purpose="probe")
    t0 = time.monotonic()
    first_partial_ms: int | None = None
    partial_lags: list[int] = []
    final_lag_ms: int | None = None
    audio_end_s = len(pcm) / BYTES_PER_SECOND

    async def consume() -> None:
        nonlocal first_partial_ms, final_lag_ms
        async for ev in stream.events():
            t_ms = round((time.monotonic() - t0) * 1000)
            audio_ms = stream.server_processed_ms  # None until the first audioProgress
            line: dict[str, object] = {"t_s": round(t_ms / 1000, 2), "kind": ev.kind,
                                       "turn": ev.turn_id}
            if ev.kind == "partial":
                lag = t_ms - audio_ms if audio_ms is not None else None
                if first_partial_ms is None:
                    first_partial_ms = t_ms
                if lag is not None:
                    partial_lags.append(lag)
                line["lag_ms"] = lag
            if ev.kind == "final":
                final_lag_ms = t_ms - round(audio_end_s * 1000)
                line.update(start_ms=ev.start_ms, end_ms=ev.end_ms)
            if ev.kind == "error":
                line["code"] = ev.error_code
            if ev.text:
                line["text"] = ev.text
            print(json.dumps(line, ensure_ascii=False), flush=True)

    consumer = asyncio.create_task(consume())
    silence = b"\x00" * CHUNK_BYTES
    frames = [pcm[i : i + CHUNK_BYTES] for i in range(0, len(pcm), CHUNK_BYTES)]
    frames += [silence] * int(tail_silence_s * 10)  # let the endpointer close the turn
    try:
        for frame in frames:  # feed at real time, like the browser AudioWorklet
            await stream.feed(frame)
            await asyncio.sleep(len(frame) / BYTES_PER_SECOND)
    finally:
        await stream.close()
        await asyncio.wait_for(consumer, 15)
    lags = sorted(partial_lags)
    return {
        "audio_seconds_sent": round(stream.audio_seconds_sent, 2),
        "connections": stream.connections,
        "first_partial_t_ms": first_partial_ms,
        "partial_lag_ms_median": lags[len(lags) // 2] if lags else None,
        "partial_lag_ms_max": lags[-1] if lags else None,
        "final_after_audio_end_ms": final_lag_ms,
    }


async def probe_file(path: Path) -> dict[str, object]:
    t0 = time.monotonic()
    turns = await FileAsr(purpose="probe").transcribe(path.read_bytes(), first_turn_id=1)
    for t in turns:
        print(json.dumps(t.model_dump(), ensure_ascii=False))
    return {"latency_ms": round((time.monotonic() - t0) * 1000), "turns": len(turns)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--wav", type=Path, required=True)
    ap.add_argument("--max-seconds", type=float, default=10.0, help="truncate clip (default 10)")
    ap.add_argument("--tail-silence", type=float, default=1.5, help="silence appended (s)")
    ap.add_argument("--file", action="store_true", help="use POST /asr/transcribe instead")
    args = ap.parse_args()

    ledger = default_ledger()
    try:
        ledger.check_live()
    except LiveAsrError as exc:
        sys.exit(f"refusing to go live: {exc}")
    print(f"budget: {ledger.audio_seconds:.1f}/{ledger.max_audio_seconds:.0f} s used, "
          f"{ledger.connections}/{ledger.max_connections} connections", file=sys.stderr)
    try:
        if args.file:
            summary = asyncio.run(probe_file(args.wav))
        else:
            pcm = read_pcm(args.wav, args.max_seconds)
            summary = asyncio.run(probe_realtime(pcm, args.tail_silence))
    except LiveAsrError as exc:
        sys.exit(f"live ASR refused/failed: {type(exc).__name__}: {exc}")
    print(json.dumps({"summary": summary}, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

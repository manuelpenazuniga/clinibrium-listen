"""Push-to-talk fallback: `AsrFile` over POST /v1/asr/transcribe (SPECS §3.1, docs/SMOKE.md).

Multipart: `request` = JSON {model, languageBias, audioEncoding: "WAV", keywords?} and
`audio` = WAV mono 16-bit 16/24 kHz, ≤ 10 min, ≤ 32 MB.
Response: {sessionId, transcript, audioDurationMs, turns[{startMs, endMs, transcript}]}.
`turns` may be EMPTY for short clips → one Turn from the top-level `transcript`.

Budget: the WAV duration is charged to the shared `UsageLedger` BEFORE the upload (fail
closed) and one JSON line is appended per HTTP attempt. At most 3 retries with backoff,
only for network errors and 5xx. HTTP 402/429 or a quota/billing error → `LiveStopped`.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import wave
from typing import Any

import httpx

from api.listen.contracts import Turn
from api.muse.asr_realtime import (
    ASR_MODEL,
    LiveAsrError,
    LiveStopped,
    UsageLedger,
    api_key_from_env,
    default_ledger,
    load_keywords,
)

BASE_URL = "https://api.meta.ai/v1"
MAX_SECONDS = 600
MAX_BYTES = 32 * 1024 * 1024
MAX_RETRIES = 3
TIMEOUT_S = 120.0


class InvalidWav(ValueError):
    """Not a mono 16-bit 16/24 kHz WAV, or over the 10 min / 32 MB limits."""


def wav_seconds(wav: bytes) -> float:
    """Validate the WAV for the endpoint and return its duration."""
    if len(wav) > MAX_BYTES:
        raise InvalidWav("WAV over 32 MB")
    try:
        with wave.open(io.BytesIO(wav)) as w:
            ch, width, rate, frames = (w.getnchannels(), w.getsampwidth(), w.getframerate(),
                                       w.getnframes())
    except (wave.Error, EOFError) as exc:
        raise InvalidWav(f"not a PCM WAV: {exc}") from None
    if ch != 1 or width != 2 or rate not in (16_000, 24_000):
        raise InvalidWav(f"need mono 16-bit 16/24 kHz, got {ch} ch, {8 * width} bit, {rate} Hz")
    seconds = frames / rate
    if seconds > MAX_SECONDS:
        raise InvalidWav("WAV over 10 min")
    return seconds


def parse_response(data: dict[str, Any], first_turn_id: int) -> list[Turn]:
    """Map the transcribe response to Turns (with the empty-`turns` fallback)."""
    out: list[Turn] = []
    for item in data.get("turns") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("transcript") or item.get("text") or "").strip()
        if not text:
            continue
        start = int(item.get("startMs") or 0)
        end = int(item.get("endMs") or start)
        out.append(Turn(turn_id=first_turn_id + len(out), start_ms=start, end_ms=end, text=text))
    if not out:
        text = str(data.get("transcript") or "").strip()
        if text:
            out.append(Turn(turn_id=first_turn_id, start_ms=0,
                            end_ms=int(data.get("audioDurationMs") or 0), text=text))
    return out


def _is_quota_error(status: int, body: str) -> bool:
    low = body.lower()
    return status in (402, 429) or any(w in low for w in ("quota", "billing", "insufficient"))


class FileAsr:
    """`AsrFile` against Meta /v1/asr/transcribe."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        keywords: list[str] | None = None,
        language_bias: list[str] | None = None,
        ledger: UsageLedger | None = None,
        purpose: str = "push_to_talk",
        transport: httpx.AsyncBaseTransport | None = None,
        backoff_s: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url or os.environ.get("MODEL_API_BASE_URL", BASE_URL)
        self._keywords = load_keywords() if keywords is None else keywords
        self._language_bias = ["Spanish"] if language_bias is None else language_bias
        self._ledger = ledger
        self._purpose = purpose
        self._transport = transport
        self._backoff_s = backoff_s

    def _request_json(self) -> str:
        req: dict[str, Any] = {"model": ASR_MODEL, "audioEncoding": "WAV"}
        if self._language_bias:
            req["languageBias"] = self._language_bias
        if self._keywords:
            req["keywords"] = self._keywords
        return json.dumps(req, ensure_ascii=False)

    async def transcribe(self, wav: bytes, first_turn_id: int) -> list[Turn]:
        seconds = wav_seconds(wav)
        ledger = self._ledger or default_ledger()
        ledger.check_live()
        key = self._api_key if self._api_key is not None else api_key_from_env()
        token = key if key.lower().startswith("bearer ") else f"Bearer {key}"
        last: Exception | None = None
        async with httpx.AsyncClient(base_url=self._base_url, timeout=TIMEOUT_S,
                                     transport=self._transport,
                                     headers={"Authorization": token}) as client:
            for attempt in range(MAX_RETRIES + 1):
                if attempt:
                    await asyncio.sleep(self._backoff_s * 2 ** (attempt - 1))
                ledger.charge(seconds)  # every attempt is billable audio: charge first
                try:
                    r = await client.post("/asr/transcribe", files={
                        "request": (None, self._request_json(), "application/json"),
                        "audio": ("audio.wav", wav, "audio/wav"),
                    })
                except httpx.TransportError as exc:
                    ledger.record("transcribe", seconds, self._purpose,
                                  f"network:{type(exc).__name__}")
                    last = exc
                    continue
                ledger.record("transcribe", seconds, self._purpose, f"http_{r.status_code}")
                if r.status_code == 200:
                    return parse_response(r.json(), first_turn_id)
                if _is_quota_error(r.status_code, r.text[:500]):
                    ledger.stop(f"HTTP {r.status_code} on transcribe")
                    raise LiveStopped(f"HTTP {r.status_code} on /asr/transcribe")
                if r.status_code < 500:
                    raise LiveAsrError(f"/asr/transcribe HTTP {r.status_code}")
                last = LiveAsrError(f"/asr/transcribe HTTP {r.status_code}")
        raise LiveAsrError(f"/asr/transcribe failed after {MAX_RETRIES} retries: {last}")


__all__ = ["FileAsr", "InvalidWav", "parse_response", "wav_seconds"]

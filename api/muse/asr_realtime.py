"""Live `AsrStream` over Meta Muse Voice Transcribe realtime (SPECS §3.1, §7 B1).

Wire protocol (wss://api.meta.ai/v1/asr/realtime):
- first frame (text, sent right after connect, < 10 s):
  {"authorization": {"accessToken": "Bearer <key>"}, "model": "muse-voice-transcribe-1.0",
   "audioEncoding": "PCM_16KHZ", "mode": "ENDPOINTING", "partialMode": "CUMULATIVE",
   "languageBias": ["Spanish"], "keywords": [...], "emitAudioProgress": true}
- audio: binary frames of raw PCM16 LE mono 16 kHz, paced at real time;
- server events (text, JSON, tagged by "type"): handshake ack {sessionId}, speechStart {turnId},
  transcript {transcript, turnId?, final?} (cumulative partial), speechEnd {turnId},
  speechComplete {turnId, transcript} (the turn's final text), audioProgress {audioProcessedMs},
  error {...};
- end of input: {"type": "endStream"}; the server then closes with 1000.
  Close 1013 = stream limit; 1011 = server error (both retryable once); 1008 = policy/auth.

Budget (fail closed): every live connection and every second of audio goes through
`UsageLedger`, which reads MUSE_MAX_AUDIO_SECONDS (unset or 0 → live disabled) and appends
one JSON line per call to fixtures/usage/1B1.jsonl (no transcripts, no keys).

Resilience: at most ONE reconnect per stream. Two 1013 closes → `LiveStopped`: live ASR is
disabled for the rest of the process (report it; do not retry).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from api.muse.interfaces import AsrEvent

ROOT = Path(__file__).resolve().parents[2]

REALTIME_URL = "wss://api.meta.ai/v1/asr/realtime"
ASR_MODEL = "muse-voice-transcribe-1.0"
SAMPLE_RATE = 16_000
BYTES_PER_SECOND = SAMPLE_RATE * 2  # PCM16 mono
CHUNK_BYTES = BYTES_PER_SECOND // 10  # 100 ms frames
MAX_AHEAD_S = 0.5  # pacing lead; the API rejects audio > 5 s ahead of real time
HANDSHAKE_TIMEOUT_S = 10.0
DRAIN_TIMEOUT_S = 10.0
DEFAULT_MAX_CONNECTIONS = 30
KEYWORDS_PATH = ROOT / "config" / "asr_keywords.json"
DEFAULT_USAGE_LOG = ROOT / "fixtures" / "usage" / "1B1.jsonl"

CLOSE_NORMAL = 1000
CLOSE_POLICY = 1008
CLOSE_SERVER_ERROR = 1011
CLOSE_STREAM_LIMIT = 1013
_RETRYABLE_CLOSES = frozenset({CLOSE_SERVER_ERROR, CLOSE_STREAM_LIMIT})


# ------------------------------------------------------------------- errors


class LiveAsrError(RuntimeError):
    """Base class: the live ASR path refused or failed."""


class LiveDisabled(LiveAsrError):
    """MUSE_MAX_AUDIO_SECONDS unset/0 or MODEL_API_KEY missing: no live calls at all."""


class BudgetExceeded(LiveAsrError):
    """The audio-seconds or connection cap would be exceeded."""


class LiveStopped(LiveAsrError):
    """Quota/billing error, HTTP 402/429 or 1013 twice: stop live work and report it."""


# ------------------------------------------------------------------- budget


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class UsageLedger:
    """Fail-closed budget guard + JSONL usage log (one line per live call).

    Totals are the sum of the log file (previous runs) plus everything charged in this
    process, so the cap holds across runs. Audio is charged *before* it is sent.
    """

    path: Path = DEFAULT_USAGE_LOG
    max_audio_seconds: float = 0.0
    max_connections: int = DEFAULT_MAX_CONNECTIONS
    _seconds: float = field(default=0.0, init=False)
    _connections: int = field(default=0, init=False)
    _stopped: str | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._seconds += float(row.get("audio_seconds") or 0)
                if row.get("endpoint") == "realtime" and row.get("status") == "open":
                    self._connections += 1

    @classmethod
    def from_env(cls) -> UsageLedger:
        raw = os.environ.get("MUSE_MAX_AUDIO_SECONDS", "").strip()
        try:
            cap = float(raw) if raw else 0.0
        except ValueError:
            cap = 0.0
        conns = os.environ.get("MUSE_MAX_REALTIME_CONNECTIONS", "").strip()
        path = os.environ.get("MUSE_USAGE_LOG", "").strip()
        return cls(
            path=Path(path) if path else DEFAULT_USAGE_LOG,
            max_audio_seconds=cap,
            max_connections=int(conns) if conns.isdigit() else DEFAULT_MAX_CONNECTIONS,
        )

    @property
    def audio_seconds(self) -> float:
        return self._seconds

    @property
    def connections(self) -> int:
        return self._connections

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.max_audio_seconds - self._seconds)

    def check_live(self) -> None:
        if self.max_audio_seconds <= 0:
            raise LiveDisabled("MUSE_MAX_AUDIO_SECONDS unset or 0: live ASR disabled")
        if self._stopped:
            raise LiveStopped(f"live ASR stopped: {self._stopped}")

    def open_connection(self, purpose: str) -> None:
        """Reserve one realtime connection (counted even if the connect then fails)."""
        with self._lock:
            self.check_live()
            if self._connections >= self.max_connections:
                raise BudgetExceeded(f"realtime connection cap {self.max_connections} reached")
            if self.remaining_seconds <= 0:
                raise BudgetExceeded("audio-seconds cap reached")
            self._connections += 1
        self.record("realtime", 0.0, purpose, "open")

    def charge(self, seconds: float) -> None:
        """Reserve `seconds` of audio before sending it; raises if over the cap."""
        with self._lock:
            self.check_live()
            if self._seconds + seconds > self.max_audio_seconds + 1e-9:
                raise BudgetExceeded(
                    f"audio cap {self.max_audio_seconds:.0f} s would be exceeded "
                    f"({self._seconds:.1f} s used)")
            self._seconds += seconds

    def stop(self, reason: str) -> None:
        self._stopped = reason

    def record(self, endpoint: str, audio_seconds: float, purpose: str, status: str) -> None:
        """Append one usage row. `audio_seconds` here must already have been `charge`d."""
        row = {"ts": _now_iso(), "endpoint": endpoint, "model": ASR_MODEL,
               "audio_seconds": round(audio_seconds, 2), "purpose": purpose, "status": status}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps(row) + "\n")


_DEFAULT_LEDGER: UsageLedger | None = None


def default_ledger() -> UsageLedger:
    """Process-wide ledger from the environment (shared by realtime and file ASR)."""
    global _DEFAULT_LEDGER
    if _DEFAULT_LEDGER is None:
        _DEFAULT_LEDGER = UsageLedger.from_env()
    return _DEFAULT_LEDGER


def api_key_from_env() -> str:
    key = os.environ.get("MODEL_API_KEY", "").strip()
    if not key:
        raise LiveDisabled("MODEL_API_KEY not set")
    return key


def load_keywords(path: Path = KEYWORDS_PATH) -> list[str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return [k for k in data.get("keywords", []) if isinstance(k, str) and k.strip()]


def config_frame(api_key: str, keywords: list[str], language_bias: list[str]) -> dict[str, Any]:
    token = api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
    frame: dict[str, Any] = {
        "authorization": {"accessToken": token},
        "model": ASR_MODEL,
        "audioEncoding": "PCM_16KHZ",
        "mode": "ENDPOINTING",
        "partialMode": "CUMULATIVE",
        "emitAudioProgress": True,
    }
    if language_bias:
        frame["languageBias"] = language_bias
    if keywords:
        frame["keywords"] = keywords
    return frame


# ------------------------------------------------------------- websocket glue


class WsConn(Protocol):
    """The subset of `websockets.asyncio.client.ClientConnection` this module uses."""

    close_code: int | None

    async def send(self, message: str | bytes) -> None: ...

    async def recv(self) -> str | bytes: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


Connector = Callable[[str], Awaitable[WsConn]]


async def _default_connect(url: str) -> WsConn:
    from websockets.asyncio.client import connect

    ws = await connect(url, open_timeout=HANDSHAKE_TIMEOUT_S, max_size=2**22)
    return ws  # type: ignore[return-value]


def _close_code(exc: BaseException, ws: WsConn | None) -> int | None:
    rcvd = getattr(exc, "rcvd", None)
    if rcvd is not None and getattr(rcvd, "code", None) is not None:
        return int(rcvd.code)
    return ws.close_code if ws is not None else None


# ------------------------------------------------------------------- stream


@dataclass
class _Turn:
    turn_id: int
    start_ms: int | None = None
    partial: str = ""
    final: str | None = None
    end_ms: int | None = None
    ended: bool = False
    started: bool = False
    done: bool = False


_SENTINEL = object()


class RealtimeAsrStream:
    """`AsrStream` against Meta realtime ASR. Lazy: connects on the first `feed`/`events`.

    `feed(pcm)` charges the budget then queues audio; a sender task paces it at real time.
    `events()` yields normalized `AsrEvent`s; it ends after `close()` (or a fatal error,
    reported as one `error` event).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        url: str = REALTIME_URL,
        keywords: list[str] | None = None,
        language_bias: list[str] | None = None,
        first_turn_id: int = 1,
        ledger: UsageLedger | None = None,
        purpose: str = "session",
        connect: Connector | None = None,
        pace: bool = True,
    ) -> None:
        self._api_key = api_key
        self._url = url
        self._keywords = load_keywords() if keywords is None else keywords
        self._language_bias = ["Spanish"] if language_bias is None else language_bias
        self._next_turn_id = first_turn_id
        self._ledger = ledger
        self._purpose = purpose
        self._connect = connect or _default_connect
        self._pace = pace

        self._audio_q: asyncio.Queue[bytes | object] = asyncio.Queue()
        self._out_q: asyncio.Queue[AsrEvent | object] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._closing = False
        self._finished = False
        self._fed_s = 0.0  # audio charged by this stream
        self._sent_s = 0.0  # audio actually sent (all connections)
        self._processed_ms: int | None = None  # last audioProcessedMs (per connection offset)
        self._conn_offset_ms = 0  # audio sent before the current connection
        self._turns: dict[str, _Turn] = {}  # provider turnId (namespaced) → turn
        self._generation = 0
        self._reconnects = 0
        self._closes_1013 = 0
        self.session_ids: list[str] = []
        self.connections = 0

    # -- public API ----------------------------------------------------------

    async def feed(self, pcm: bytes) -> None:
        if self._closing or self._finished or not pcm:
            return
        seconds = len(pcm) / BYTES_PER_SECOND
        ledger = self._get_ledger()
        try:
            ledger.charge(seconds)  # fail closed: nothing is queued past the cap
        except LiveAsrError as exc:
            if self._task is None:
                raise  # nothing started: refuse loudly
            # mid-stream: end this stream with one error event; the session keeps running
            self._emit(AsrEvent(kind="error", error_code=type(exc).__name__))
            self._closing = True
            self._audio_q.put_nowait(_SENTINEL)
            return
        self._fed_s += seconds
        self._ensure_started()
        for i in range(0, len(pcm), CHUNK_BYTES):
            self._audio_q.put_nowait(pcm[i : i + CHUNK_BYTES])

    async def events(self) -> AsyncIterator[AsrEvent]:
        # no connection is opened until audio arrives (saves the connection budget)
        while True:
            item = await self._out_q.get()
            if item is _SENTINEL:
                return
            assert isinstance(item, AsrEvent)
            yield item

    async def close(self) -> None:
        if self._closing:
            if self._task is not None:
                with contextlib.suppress(Exception):
                    await self._task
            return
        self._closing = True
        if self._task is None:  # never started: nothing was sent
            self._finish()
            return
        self._audio_q.put_nowait(_SENTINEL)
        try:
            await asyncio.wait_for(asyncio.shield(self._task), DRAIN_TIMEOUT_S + 2)
        except (TimeoutError, Exception):
            self._task.cancel()
            with contextlib.suppress(BaseException):
                await self._task
            self._finish()

    @property
    def audio_seconds_sent(self) -> float:
        return self._sent_s

    @property
    def server_processed_ms(self) -> int | None:
        """Audio position the server reports as processed (audioProgress), if any."""
        if self._processed_ms is None:
            return None
        return self._conn_offset_ms + self._processed_ms

    # -- internals -----------------------------------------------------------

    def _get_ledger(self) -> UsageLedger:
        if self._ledger is None:
            self._ledger = default_ledger()
        return self._ledger

    def _ensure_started(self) -> None:
        if self._task is None and not self._finished:
            self._task = asyncio.get_running_loop().create_task(self._run())

    def _emit(self, ev: AsrEvent) -> None:
        self._out_q.put_nowait(ev)

    def _finish(self) -> None:
        if not self._finished:
            self._finished = True
            self._out_q.put_nowait(_SENTINEL)

    def _audio_ms(self) -> int:
        if self._processed_ms is not None:
            return self._conn_offset_ms + self._processed_ms
        return round(self._sent_s * 1000)

    async def _run(self) -> None:
        try:
            while True:
                outcome = await self._run_connection()
                if outcome is None:
                    return  # clean end
                code, reason = outcome
                if code == CLOSE_STREAM_LIMIT:
                    self._closes_1013 += 1
                    if self._closes_1013 >= 2:
                        self._get_ledger().stop("close 1013 twice (stream limit)")
                        self._emit(AsrEvent(kind="error", error_code="1013_repeated"))
                        return
                retryable = code in _RETRYABLE_CLOSES or code is None
                if self._closing or not retryable or self._reconnects >= 1:
                    self._emit(AsrEvent(kind="error", error_code=reason))
                    return
                self._reconnects += 1
                self._drop_open_turns()
                await asyncio.sleep(0.5)
        except LiveAsrError as exc:
            self._emit(AsrEvent(kind="error", error_code=type(exc).__name__))
        except Exception as exc:  # never crash the session on ASR failure
            self._emit(AsrEvent(kind="error", error_code=f"internal:{type(exc).__name__}"))
        finally:
            self._finish()

    def _drop_open_turns(self) -> None:
        """A dropped connection loses in-flight turns; close them so the UI resets."""
        for t in self._turns.values():
            if t.started and not t.done:
                self._emit(AsrEvent(kind="speech_end", turn_id=t.turn_id,
                                    end_ms=self._audio_ms()))
                t.done = True
        self._turns.clear()

    async def _run_connection(self) -> tuple[int | None, str] | None:
        """One websocket connection. Returns None on a clean end, else (close code, reason)."""
        ledger = self._get_ledger()
        key = self._api_key if self._api_key is not None else api_key_from_env()
        ledger.open_connection(self._purpose)  # raises before any network I/O
        self.connections += 1
        self._generation += 1
        self._conn_offset_ms = round(self._sent_s * 1000)
        self._processed_ms = None
        conn_start_s = self._sent_s
        status = "closed"
        ws: WsConn | None = None
        try:
            try:
                ws = await asyncio.wait_for(self._connect(self._url), HANDSHAKE_TIMEOUT_S)
                await ws.send(json.dumps(
                    config_frame(key, self._keywords, self._language_bias),
                    ensure_ascii=False))
            except Exception as exc:
                status = f"connect_failed:{type(exc).__name__}"
                code = _status_code(exc)
                if code in (402, 429):
                    ledger.stop(f"HTTP {code} on realtime connect")
                    raise LiveStopped(f"HTTP {code}") from None
                if code is not None and 400 <= code < 500:
                    return (CLOSE_POLICY, f"http_{code}")  # auth/request error: no retry
                return (None, status)

            end_sent = asyncio.Event()
            sender = asyncio.create_task(self._send_loop(ws, end_sent))
            try:
                result = await self._recv_loop(ws, end_sent)
            finally:
                sender.cancel()
                with contextlib.suppress(BaseException):
                    await sender
            if result is not None:
                status = f"close:{result[0]}"
            return result
        finally:
            if ws is not None:
                with contextlib.suppress(Exception):
                    await ws.close()
            # audio was charged (conservatively) at feed(); the row logs what was sent
            ledger.record("realtime", self._sent_s - conn_start_s, self._purpose, status)

    async def _send_loop(self, ws: WsConn, end_sent: asyncio.Event) -> None:
        loop = asyncio.get_running_loop()
        origin = loop.time()
        sent_here = 0.0
        while True:
            item = await self._audio_q.get()
            if item is _SENTINEL:
                await ws.send(json.dumps({"type": "endStream"}))
                end_sent.set()
                return
            assert isinstance(item, bytes)
            if self._pace:
                lead = origin + sent_here - loop.time()
                if lead > MAX_AHEAD_S:
                    await asyncio.sleep(lead - MAX_AHEAD_S)
                elif lead < -1.0:  # input stalled (mic idle): re-anchor, never burst ahead
                    origin = loop.time() - sent_here
            await ws.send(item)
            dur = len(item) / BYTES_PER_SECOND
            sent_here += dur
            self._sent_s += dur

    async def _recv_loop(self, ws: WsConn,
                         end_sent: asyncio.Event) -> tuple[int | None, str] | None:
        from websockets.exceptions import ConnectionClosed

        while True:
            try:
                if end_sent.is_set():
                    raw = await asyncio.wait_for(ws.recv(), DRAIN_TIMEOUT_S)
                else:
                    raw = await ws.recv()
            except ConnectionClosed as exc:
                code = _close_code(exc, ws)
                if code == CLOSE_NORMAL and end_sent.is_set():
                    self._flush_turns()
                    return None
                if code == CLOSE_NORMAL:
                    code = None  # server ended early: treat as retryable drop
                return (code, f"close_{code}")
            except TimeoutError:
                self._flush_turns()
                return None  # drained long enough after endStream
            if isinstance(raw, bytes):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict):
                self._handle(msg)

    # -- event mapping -------------------------------------------------------

    def _turn(self, provider_id: object) -> _Turn:
        key = f"{self._generation}:{provider_id}"
        t = self._turns.get(key)
        if t is None:
            t = _Turn(turn_id=self._next_turn_id)
            self._next_turn_id += 1
            self._turns[key] = t
        return t

    def _active_turn(self) -> _Turn | None:
        open_turns = [t for t in self._turns.values() if t.started and not t.ended]
        return open_turns[-1] if open_turns else None

    def _start(self, t: _Turn, ms: int | None) -> None:
        if not t.started:
            t.started = True
            t.start_ms = ms if ms is not None else self._audio_ms()
            self._emit(AsrEvent(kind="speech_start", turn_id=t.turn_id, start_ms=t.start_ms))

    def _handle(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        sid = msg.get("sessionId")
        if isinstance(sid, str) and sid and sid not in self.session_ids:
            self.session_ids.append(sid)
        if kind == "audioProgress":
            ms = msg.get("audioProcessedMs")
            if isinstance(ms, int | float) and not isinstance(ms, bool) and ms >= 0:
                self._processed_ms = int(ms)
            return
        if kind == "error":
            code = msg.get("code") or msg.get("errorCode") or msg.get("error") or "server_error"
            code_s = str(code)[:80]
            if any(w in code_s.lower() for w in ("quota", "billing", "payment", "402", "429")):
                self._get_ledger().stop(f"server error {code_s}")
            self._emit(AsrEvent(kind="error", error_code=code_s))
            return
        start_ms = _int(msg.get("startMs"))
        end_ms = _int(msg.get("endMs"))
        tid = msg.get("turnId")
        if kind == "speechStart" and tid is not None:
            self._start(self._turn(tid), start_ms)
        elif kind == "transcript":
            text = msg.get("transcript")
            if not isinstance(text, str):
                return
            t = self._turn(tid) if tid is not None else self._active_turn()
            if t is None or t.done or t.final is not None or not text.strip():
                return
            self._start(t, start_ms)
            if text != t.partial:
                t.partial = text
                self._emit(AsrEvent(kind="partial", turn_id=t.turn_id, text=text,
                                    start_ms=t.start_ms))
        elif kind == "speechEnd" and tid is not None:
            t = self._turn(tid)
            t.ended = True
            t.end_ms = end_ms if end_ms is not None else self._audio_ms()
            self._maybe_done(t)
        elif kind == "speechComplete" and tid is not None:
            text = msg.get("transcript")
            t = self._turn(tid)
            if t.done or not isinstance(text, str):
                return
            self._start(t, start_ms)
            t.final = text.strip()
            if end_ms is not None:
                t.end_ms = end_ms
            self._maybe_done(t)

    def _maybe_done(self, t: _Turn) -> None:
        """Emit final then speech_end once both speechComplete and speechEnd arrived."""
        if t.done or t.final is None or not t.ended:
            return
        t.done = True
        end = t.end_ms if t.end_ms is not None else self._audio_ms()
        if t.final:
            self._emit(AsrEvent(kind="final", turn_id=t.turn_id, text=t.final,
                                start_ms=t.start_ms, end_ms=end))
        self._emit(AsrEvent(kind="speech_end", turn_id=t.turn_id, end_ms=end))

    def _flush_turns(self) -> None:
        """Stream ended: finish turns that got speechComplete but no speechEnd (or v.v.)."""
        for t in self._turns.values():
            if t.done or not t.started:
                continue
            if t.final is None and t.partial:
                t.final = t.partial  # last cumulative partial is the best text we have
            t.ended = True
            if t.final is None:
                t.final = ""
            self._maybe_done(t)


def _int(v: object) -> int | None:
    if isinstance(v, bool) or not isinstance(v, int | float):
        return None
    return int(v)


def _status_code(exc: BaseException) -> int | None:
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    return int(code) if isinstance(code, int) else None


def open_realtime_stream(**kwargs: Any) -> RealtimeAsrStream:
    """Factory for `Providers.open_asr` (wired by 1B2 / Phase 2)."""
    return RealtimeAsrStream(**kwargs)


__all__ = [
    "ASR_MODEL",
    "BudgetExceeded",
    "LiveAsrError",
    "LiveDisabled",
    "LiveStopped",
    "REALTIME_URL",
    "RealtimeAsrStream",
    "UsageLedger",
    "api_key_from_env",
    "config_frame",
    "default_ledger",
    "load_keywords",
    "open_realtime_stream",
]

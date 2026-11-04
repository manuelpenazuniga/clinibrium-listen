"""Meta Model API client for the Muse LLM roles (SPECS §3.1, §7 api/muse/).

One entry point for every model call: `MuseClient.complete()`. It builds the
OpenAI-compatible chat request (strict `json_schema` response format), computes
the request's *replay key*, and hands it to a transport:

- `LiveTransport`  → the real API (`openai` SDK, base_url https://api.meta.ai/v1,
  key from `MODEL_API_KEY`). Every HTTP attempt goes through `BudgetGuard`
  first (fails closed) and appends one line to the usage ledger. With
  `MUSE_RECORD=1` each successful exchange is written to
  `fixtures/replays/<case>/<replay_key>.json`.
- `ReplayTransport` (api/muse/replay.py) → serves those recordings, no network.

Budget (fail closed — unset or 0 means "live disabled"):
    MUSE_MAX_LIVE_CALLS    total live attempts, all roles
    MUSE_MAX_WONDER_CALLS  attempts to muse-wonder-1.0
    MUSE_MAX_VISION_CALLS  image attempts (default 10, never more than 10)
Counts are read from the usage ledger, so caps hold across processes.
On HTTP 402, a quota/billing error, or a 429/5xx that survives the retries, the
process latches into a stopped state and refuses all further live calls.

The key is only read from the environment and is never logged or recorded.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

from api.listen.contracts import strict_json_schema

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
REPLAYS_DIR = ROOT / "fixtures" / "replays"
DEFAULT_LEDGER = ROOT / "fixtures" / "usage" / "1B2.jsonl"

BASE_URL = "https://api.meta.ai/v1"
SPARK = "muse-spark-1.3"
WONDER = "muse-wonder-1.0"

Role = Literal["extractor", "phraser", "advocate", "vision", "reasoner"]
Effort = Literal["minimal", "low", "medium", "high"]

# Per-role limits (session budget rules). max_completion_tokens is a hard cap.
ROLE_LIMITS: dict[str, tuple[int, Effort]] = {
    "extractor": (1500, "minimal"),
    "phraser": (1000, "minimal"),
    "vision": (1500, "low"),
    "advocate": (2500, "medium"),
    "reasoner": (2500, "medium"),
}
HARD_VISION_CAP = 10
MAX_RETRIES = 3
TIMEOUT_S = 45.0

M = TypeVar("M", bound=BaseModel)


class MuseError(RuntimeError):
    """Base class for Muse client errors."""


class BudgetExceeded(MuseError):
    """Live call refused by the budget guard (caps unset, zero or exhausted)."""


class QuotaStop(MuseError):
    """Billing/quota/rate error from Meta: live work is stopped for this process."""


class MuseSchemaError(MuseError):
    """The model returned content that does not validate against the schema."""


class ReplayMiss(MuseError):
    """MUSE_MODE=replay and no recording matches the request's replay key."""


# ------------------------------------------------------------------ prompts


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def prompt_sha256(name: str) -> str:
    return hashlib.sha256(load_prompt(name).encode("utf-8")).hexdigest()


def prompt_hashes() -> dict[str, str]:
    """role → SHA-256 of its prompt file (for the receipt, SPECS §7 receipt.py)."""
    return {p.stem: prompt_sha256(p.stem) for p in sorted(PROMPTS_DIR.glob("*.md"))}


# ------------------------------------------------------------------ request


def canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class ChatRequest:
    role: Role
    model: str
    messages: list[dict[str, Any]]
    schema_name: str
    schema: dict[str, Any]
    max_completion_tokens: int
    reasoning_effort: Effort
    replay_key: str  # sha256 over the role's semantic inputs (see replay_key())
    has_image: bool = False
    # Replay-only fallbacks, tried in order when `replay_key` has no recording
    # (e.g. the same turn recorded without a pending question). Never recorded.
    alt_replay_keys: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": self.messages,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": self.schema_name, "schema": self.schema, "strict": True}},
            "max_completion_tokens": self.max_completion_tokens,
            "reasoning_effort": self.reasoning_effort,
        }

    def redacted_messages(self) -> list[dict[str, Any]]:
        """Messages for recordings: image bytes replaced by their SHA-256."""
        out: list[dict[str, Any]] = []
        for m in self.messages:
            content = m.get("content")
            if isinstance(content, list):
                parts = []
                for p in content:
                    if p.get("type") == "image_url":
                        url = p["image_url"]["url"]
                        digest = hashlib.sha256(url.encode()).hexdigest()
                        parts.append({"type": "image_url", "image_url": {
                            "url": f"<image sha256-of-data-url={digest}>"}})
                    else:
                        parts.append(p)
                out.append({**m, "content": parts})
            else:
                out.append(m)
        return out


def replay_key(role: str, model: str, prompt_name: str, inputs: Any) -> str:
    """Stable key for a request: role + model + prompt hash + the role's semantic inputs.

    Each role passes only the inputs its answer depends on (e.g. the extractor's
    new-turn text and pending-question key), so a replay keeps matching when the
    orchestrator changes incidental context (question ids, ordering)."""
    blob = canonical({"role": role, "model": model, "prompt": prompt_sha256(prompt_name),
                      "inputs": inputs})
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChatResult:
    content: str
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0


class Transport(Protocol):
    async def send(self, req: ChatRequest) -> ChatResult: ...


# ------------------------------------------------------------- budget/ledger


def _env_int(name: str) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else 0
    except ValueError:
        return 0


class BudgetGuard:
    """Fail-closed caps on live attempts, counted from the usage ledger."""

    def __init__(self, ledger: Path | None = None) -> None:
        env_ledger = os.environ.get("MUSE_USAGE_LEDGER")
        self.ledger = ledger or (Path(env_ledger) if env_ledger else DEFAULT_LEDGER)
        self.stopped: str | None = None

    def counts(self) -> dict[str, int]:
        total = wonder = vision = 0
        if self.ledger.exists():
            for line in self.ledger.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                total += 1
                wonder += row.get("model") == WONDER
                vision += row.get("role") == "vision"
        return {"total": total, "wonder": wonder, "vision": vision}

    def check(self, req: ChatRequest) -> None:
        if self.stopped:
            raise QuotaStop(f"live work stopped earlier in this process: {self.stopped}")
        max_total = _env_int("MUSE_MAX_LIVE_CALLS")
        if max_total <= 0:
            raise BudgetExceeded("live calls disabled: set MUSE_MAX_LIVE_CALLS > 0")
        c = self.counts()
        if c["total"] >= max_total:
            raise BudgetExceeded(f"MUSE_MAX_LIVE_CALLS={max_total} exhausted")
        if req.model == WONDER:
            max_wonder = _env_int("MUSE_MAX_WONDER_CALLS")
            if max_wonder <= 0:
                raise BudgetExceeded("wonder calls disabled: set MUSE_MAX_WONDER_CALLS > 0")
            if c["wonder"] >= max_wonder:
                raise BudgetExceeded(f"MUSE_MAX_WONDER_CALLS={max_wonder} exhausted")
        if req.has_image:
            raw = os.environ.get("MUSE_MAX_VISION_CALLS", "").strip()
            max_vision = min(HARD_VISION_CAP, _env_int("MUSE_MAX_VISION_CALLS") if raw
                             else HARD_VISION_CAP)
            if c["vision"] >= max_vision:
                raise BudgetExceeded(f"vision cap {max_vision} exhausted")

    def record(self, req: ChatRequest, usage: dict[str, int], latency_ms: int,
               status: str) -> None:
        """One JSON line per attempt. No text, no keys."""
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "role": req.role, "model": req.model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "reasoning_tokens": usage.get("reasoning_tokens", 0),
            "latency_ms": latency_ms, "status": status,
        }
        with self.ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")


# ------------------------------------------------------------------ live


def _usage(obj: Any) -> dict[str, int]:
    if obj is None:
        return {}
    details = getattr(obj, "completion_tokens_details", None)
    return {
        "prompt_tokens": int(getattr(obj, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(obj, "completion_tokens", 0) or 0),
        "reasoning_tokens": int(getattr(details, "reasoning_tokens", 0) or 0) if details else 0,
    }


def _retry_after(headers: Any) -> float | None:
    try:
        raw = headers.get("retry-after") if headers is not None else None
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


_QUOTA_WORDS = ("quota", "billing", "insufficient", "credit", "payment")


def record_exchange(req: ChatRequest, result: ChatResult, case: str | None = None) -> Path:
    """Write one replay fixture (redacted turns only; never the key)."""
    case = case or os.environ.get("MUSE_REPLAY_CASE", "default")
    path = REPLAYS_DIR / case / f"{req.replay_key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "replay_key": req.replay_key, "role": req.role, "model": req.model,
        "reasoning_effort": req.reasoning_effort,
        "max_completion_tokens": req.max_completion_tokens,
        "messages": req.redacted_messages(),
        "response": {"content": result.content, "usage": result.usage,
                     "latency_ms": result.latency_ms},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


class LiveTransport:
    """The only path to the network. Budget-guarded, ledgered, bounded retries."""

    def __init__(self, guard: BudgetGuard | None = None, sdk: Any = None,
                 sleep: Any = asyncio.sleep) -> None:
        self.guard = guard or BudgetGuard()
        self._sdk = sdk
        self._sleep = sleep

    def _client(self) -> Any:
        if self._sdk is None:
            key = os.environ.get("MODEL_API_KEY", "")
            if not key:
                raise MuseError("MODEL_API_KEY is not set")
            from openai import AsyncOpenAI

            self._sdk = AsyncOpenAI(api_key=key, base_url=os.environ.get(
                "MODEL_API_BASE_URL", BASE_URL), timeout=TIMEOUT_S, max_retries=0)
        return self._sdk

    async def send(self, req: ChatRequest) -> ChatResult:
        import openai

        sdk = self._client()
        last: str = ""
        for attempt in range(MAX_RETRIES + 1):
            self.guard.check(req)  # every attempt counts against the caps
            t0 = time.monotonic()
            wait: float | None = None
            try:
                resp = await sdk.chat.completions.create(**req.payload())
            except openai.APIStatusError as exc:
                ms = round((time.monotonic() - t0) * 1000)
                self.guard.record(req, {}, ms, f"http_{exc.status_code}")
                body = str(getattr(exc, "message", "")).lower()
                if exc.status_code == 402 or any(w in body for w in _QUOTA_WORDS):
                    self.guard.stopped = f"HTTP {exc.status_code} quota/billing"
                    raise QuotaStop(self.guard.stopped) from None
                if exc.status_code == 429 or exc.status_code >= 500:
                    last = f"HTTP {exc.status_code}"
                    wait = _retry_after(getattr(exc.response, "headers", None))
                else:
                    raise MuseError(f"{req.role}: HTTP {exc.status_code}") from None
            except (openai.APITimeoutError, openai.APIConnectionError) as exc:
                ms = round((time.monotonic() - t0) * 1000)
                self.guard.record(req, {}, ms, type(exc).__name__)
                last = type(exc).__name__
            else:
                ms = round((time.monotonic() - t0) * 1000)
                usage = _usage(getattr(resp, "usage", None))
                content = resp.choices[0].message.content or ""
                self.guard.record(req, usage, ms, "ok")
                result = ChatResult(content=content, usage=usage, latency_ms=ms)
                if os.environ.get("MUSE_RECORD") == "1":
                    record_exchange(req, result)
                return result
            if attempt < MAX_RETRIES:
                backoff = min(20.0, 1.0 * 2 ** attempt) * (0.5 + random.random())
                await self._sleep(max(backoff, wait or 0.0))
        if last.startswith("HTTP 429") or last.startswith("HTTP 5"):
            self.guard.stopped = f"{last} after {MAX_RETRIES} retries"
            raise QuotaStop(self.guard.stopped)
        raise MuseError(f"{req.role}: {last} after {MAX_RETRIES} retries")


# ---------------------------------------------------------------- client


class MuseClient:
    """Builds strict-schema requests and parses the answer into the contract model."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    async def complete(self, *, role: Role, model: str, system: str, user: Any,
                       out: type[M], key_inputs: Any, prompt_name: str,
                       image_data_url: str | None = None,
                       alt_key_inputs: list[Any] | None = None) -> M:
        max_tokens, effort = ROLE_LIMITS[role]
        text = user if isinstance(user, str) else canonical(user)
        content: Any = text
        if image_data_url is not None:
            content = [{"type": "text", "text": text},
                       {"type": "image_url", "image_url": {"url": image_data_url}}]
        req = ChatRequest(
            role=role, model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": content}],
            schema_name=out.__name__.lower(), schema=strict_json_schema(out),
            max_completion_tokens=max_tokens, reasoning_effort=effort,
            replay_key=replay_key(role, model, prompt_name, key_inputs),
            has_image=image_data_url is not None,
            alt_replay_keys=tuple(replay_key(role, model, prompt_name, alt)
                                  for alt in (alt_key_inputs or [])),
        )
        result = await self.transport.send(req)
        try:
            return out.model_validate_json(result.content)
        except ValueError as exc:
            raise MuseSchemaError(f"{role}: response does not match {out.__name__}") from exc


# ------------------------------------------------------------ providers


class DailyCappedTransport:
    """Charges the server-side daily cap (api/muse/daily_cap.py) before every
    live request; the inner LiveTransport keeps its own fail-closed budget."""

    def __init__(self, inner: Transport) -> None:
        self.inner = inner

    async def send(self, req: ChatRequest) -> ChatResult:
        from api.muse.daily_cap import DailyCapExceeded, daily_cap

        try:
            daily_cap().charge("model_calls")
        except DailyCapExceeded as exc:
            raise BudgetExceeded(str(exc)) from None
        return await self.inner.send(req)


class _DailyCappedFileAsr:
    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def transcribe(self, wav: bytes, first_turn_id: int) -> Any:
        from api.muse.daily_cap import daily_cap

        daily_cap().charge("asr_streams")
        return await self.inner.transcribe(wav, first_turn_id)


def live_asr() -> tuple[Any, Any]:
    """1B1's live ASR: `RealtimeAsrStream` (lazy; connects on the first audio frame)
    and the push-to-talk `FileAsr`. Both are budget-guarded by 1B1's usage ledger
    (MUSE_MAX_AUDIO_SECONDS unset → fail closed before any network I/O), and each
    stream / file request is charged to the daily cap when it is opened."""
    from api.muse.asr_file import FileAsr
    from api.muse.asr_realtime import RealtimeAsrStream
    from api.muse.daily_cap import daily_cap

    def open_asr() -> RealtimeAsrStream:
        daily_cap().charge("asr_streams")
        return RealtimeAsrStream()

    return open_asr, _DailyCappedFileAsr(FileAsr())


def build_with_transport(mode: Literal["live", "replay"], transport: Transport) -> Any:
    from api.muse.advocate import LiveAdvocate
    from api.muse.extractor import LiveExtractor
    from api.muse.interfaces import Providers
    from api.muse.phrasing import LivePhraser
    from api.muse.reasoner import LiveReasoner
    from api.muse.vision import LiveVision

    client = MuseClient(transport)
    model_ids = {"asr": "muse-voice-transcribe-1.0", "extractor": SPARK, "phraser": SPARK,
                 "advocate": WONDER, "vision": SPARK, "reasoner_spark": SPARK,
                 "reasoner_wonder": WONDER}
    if mode == "live":
        open_asr, asr_file = live_asr()
    else:
        from api.muse import mock

        script = mock._default_script()
        open_asr = lambda: mock.MockAsrStream(script)  # noqa: E731
        asr_file = mock.MockAsrFile(script)
        model_ids["asr"] = "mock-asr"
    return Providers(
        mode=mode, open_asr=open_asr, asr_file=asr_file,
        extractor=LiveExtractor(client), phraser=LivePhraser(client),
        advocate=LiveAdvocate(client), vision=LiveVision(client),
        reasoner_spark=LiveReasoner(client, SPARK),
        reasoner_wonder=LiveReasoner(client, WONDER),
        model_ids=model_ids,
    )


def build_providers() -> Any:
    """MUSE_MODE=live provider bundle (api.muse.interfaces.get_providers)."""
    return build_with_transport("live", DailyCappedTransport(LiveTransport()))

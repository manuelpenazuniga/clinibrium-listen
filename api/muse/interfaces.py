"""Model-provider interfaces (SPECS §5.3). FROZEN after Phase 0.

Every model capability is a Protocol, so the session orchestrator never knows
whether it talks to Meta (live), to recorded fixtures (replay) or to the
deterministic fakes in `api.muse.mock`.

`get_providers(mode)` resolves a `Providers` bundle by convention:
    mock   → api.muse.mock.build_providers()
    replay → api.muse.replay.build_providers()   (workstream 1B2)
    live   → api.muse.client.build_providers()   (workstream 1B2; wires 1B1's ASR)

Models only PROPOSE field values or confirmation requests; they never set
urgency or actions (SPECS §0.8, L3). Nothing here carries urgency into state.
"""
from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from api.listen.contracts import (
    AdvocateOut,
    EngineResultView,
    ExtractorOut,
    FieldValue,
    PhrasingOut,
    Question,
    ReasonerOut,
    Turn,
    VisionOut,
)

MuseMode = Literal["mock", "replay", "live"]


class _Ctx(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ----------------------------------------------------------------------- ASR


class AsrEvent(_Ctx):
    """Normalized ASR event (Meta: speechStart / transcript / speechEnd /
    speechComplete / error)."""

    kind: Literal["speech_start", "partial", "final", "speech_end", "error"]
    turn_id: int | None = None
    text: str = ""  # partial: cumulative text of the current turn; final: the turn
    start_ms: int | None = None
    end_ms: int | None = None
    error_code: str | None = None


@runtime_checkable
class AsrStream(Protocol):
    """One realtime transcription stream (PCM16 LE mono 16 kHz in, events out)."""

    async def feed(self, pcm: bytes) -> None: ...

    def events(self) -> AsyncIterator[AsrEvent]: ...

    async def close(self) -> None: ...


@runtime_checkable
class AsrFile(Protocol):
    """Push-to-talk fallback: one WAV (mono 16-bit, 16/24 kHz) → final turns."""

    async def transcribe(self, wav: bytes, first_turn_id: int) -> list[Turn]: ...


# ---------------------------------------------------------------- contexts


class ExtractCtx(_Ctx):
    turns: list[Turn]  # redacted, final turns so far (context)
    new_turn: Turn  # the redacted turn to extract from
    catalog_keys: list[str]  # allowed keys (egress allowlist, L9)
    current_values: dict[str, FieldValue]  # non-rejected values, for corrections
    pending_question: Question | None


class QuestionDraft(_Ctx):
    id: str
    key: str
    label_es: str
    label_en: str
    enum_values: list[str] | None
    enum_labels_es: dict[str, str] | None
    reason: str


class AdvocateCtx(_Ctx):
    turns: list[Turn]
    current_values: dict[str, FieldValue]
    catalog_keys: list[str]
    result: EngineResultView | None


class VisionCtx(_Ctx):
    document_id: str
    catalog_keys: list[str]


class GroundingChunkView(_Ctx):
    chunk_id: str
    text: str


class ReasonerCtx(_Ctx):
    confirmed_values: dict[str, FieldValue]
    result: EngineResultView
    grounding: list[GroundingChunkView]
    lang: Literal["es", "en"] = "es"


# --------------------------------------------------------------- providers


@runtime_checkable
class Extractor(Protocol):
    async def extract(self, ctx: ExtractCtx) -> ExtractorOut: ...


@runtime_checkable
class Phraser(Protocol):
    async def phrase(self, q: QuestionDraft) -> PhrasingOut: ...


@runtime_checkable
class Advocate(Protocol):
    async def review(self, ctx: AdvocateCtx) -> AdvocateOut: ...


@runtime_checkable
class Vision(Protocol):
    async def read(self, image: bytes, mime: str, ctx: VisionCtx) -> VisionOut: ...


@runtime_checkable
class Reasoner(Protocol):
    model_id: str

    async def explain(self, ctx: ReasonerCtx) -> ReasonerOut: ...


@dataclass(frozen=True)
class Providers:
    mode: MuseMode
    open_asr: Callable[[], AsrStream]
    asr_file: AsrFile
    extractor: Extractor
    phraser: Phraser
    advocate: Advocate
    vision: Vision
    reasoner_spark: Reasoner
    reasoner_wonder: Reasoner
    model_ids: dict[str, str]  # role → model id, recorded in the receipt


_MODULES: dict[str, str] = {
    "mock": "api.muse.mock",
    "replay": "api.muse.replay",
    "live": "api.muse.client",
}


def get_providers(mode: MuseMode) -> Providers:
    """Resolve the provider bundle for `MUSE_MODE` (see module docstring)."""
    if mode not in _MODULES:
        raise ValueError(f"unknown MUSE_MODE {mode!r}")
    try:
        module = importlib.import_module(_MODULES[mode])
    except ModuleNotFoundError as exc:
        raise NotImplementedError(f"MUSE_MODE={mode} not implemented yet ({exc.name})") from exc
    build = getattr(module, "build_providers", None)
    if build is None:
        raise NotImplementedError(f"{_MODULES[mode]}.build_providers() missing")
    providers = build()
    if not isinstance(providers, Providers) or providers.mode != mode:
        raise TypeError(f"{_MODULES[mode]}.build_providers() returned {providers!r}")
    return providers


__all__ = [
    "Advocate",
    "AdvocateCtx",
    "AsrEvent",
    "AsrFile",
    "AsrStream",
    "ExtractCtx",
    "Extractor",
    "GroundingChunkView",
    "MuseMode",
    "Phraser",
    "Providers",
    "QuestionDraft",
    "Reasoner",
    "ReasonerCtx",
    "Vision",
    "VisionCtx",
    "get_providers",
]

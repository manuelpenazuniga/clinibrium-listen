"""Clinibrium Listen wire + model-output contracts (SPECS §5.2).

FROZEN after Phase 0. `web/lib/contracts.ts` is generated from these models by
`scripts/gen_contracts.sh`; nobody edits it by hand.

Conventions:
  - every model forbids extra keys (`extra="forbid"` → `additionalProperties:false`);
  - no floats anywhere: percentages are ints 0..100, float field values travel
    as `str` with fixed decimals (keeps the receipt's canonical JSON float-free);
  - model-output schemas (DeltaOut … ReasonerOut) are strict-JSON compatible:
    every property required, optional = nullable, no Any, no sets, no recursion.
    Use `strict_json_schema(Model)` to build the `response_format` schema.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Source = Literal["dictated", "answered", "document", "advocate", "manual"]
Status = Literal["proposed", "confirmed", "rejected"]
Urgency3 = Literal["inmediata", "prioritaria", "ambulatoria"]
FieldValue = bool | int | str  # floats stored as str with fixed decimals


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- state


class Evidence(_Strict):
    source: Source
    quote: str | None
    turn_id: int | None
    start_ms: int | None
    document_id: str | None
    confidence_pct: int  # 0..100 (int, no floats)


class FieldState(_Strict):
    key: str
    value: FieldValue
    status: Status
    evidence: list[Evidence]
    sticky_alert: bool  # True if this value escalates (SPECS §6.1)
    conflict: Conflict | None


class Conflict(_Strict):
    candidates: list[FieldState]  # competing values, kept until the clinician resolves
    note: str


# --------------------------------------------- model output schemas (strict JSON)


class DeltaOut(_Strict):
    """One item of `{"deltas": [...]}`. Exactly one `value_*` is non-null."""

    key: str  # must be in config/field_catalog.json
    value_bool: bool | None
    value_int: int | None
    value_enum: str | None
    value_text: str | None
    quote: str
    confidence_pct: int
    answers_question_id: str | None


class ExtractorOut(_Strict):
    deltas: list[DeltaOut]


class AdvocateItemOut(_Strict):
    key: str
    value_bool: bool | None
    value_int: int | None
    value_enum: str | None
    value_text: str | None
    quote: str
    rationale: str


class AdvocateOut(_Strict):
    requests: list[AdvocateItemOut]


class VisionOut(_Strict):
    deltas: list[DeltaOut]
    read_text: str


class PhrasingOut(_Strict):
    text_es: str
    text_en: str


class ReasonerOut(_Strict):
    explanation: str
    reconciliation: str
    suggested_next_steps: list[str]
    suggested_urgency: Urgency3 | None
    cited_chunk_ids: list[str]


# ------------------------------------------------------------------- session parts


class Question(_Strict):
    id: str
    key: str
    text_es: str
    text_en: str
    reason: str
    impact: int
    status: Literal["pending", "answered", "skipped"]


class ConfirmationRequest(_Strict):
    id: str
    key: str
    value: FieldValue
    quote: str
    rationale: str
    status: Literal["pending", "confirmed", "dismissed"]


class Turn(_Strict):
    turn_id: int
    start_ms: int
    end_ms: int
    text: str  # redacted


class RedFlagHitView(_Strict):
    id: str
    label: str
    severity: Literal["high", "medium"]
    provisional: bool


class DxView(_Strict):
    diagnosis: str
    score_pct: int
    provisional: bool


class EngineResultView(_Strict):
    urgency: Urgency3
    source_eval: Literal["confirmed", "confirmed_plus_proposed"]
    red_flags: list[RedFlagHitView]
    differential: list[DxView]
    forced_actions: list[str]
    blocked_actions: list[str]
    applied_rails: list[str]
    advocate_floor_active: bool
    referral_label_es: str
    referral_label_en: str
    engine_version: str


class ReasonerView(_Strict):
    model_used: str
    explanation: str
    reconciliation: str
    suggested_next_steps: list[str]
    cited_chunk_ids: list[str]
    citations_verified: bool


class LetterStatement(_Strict):
    text_es: str
    text_en: str
    keys: list[str]


class LetterSection(_Strict):
    title_es: str
    title_en: str
    statements: list[LetterStatement]


class ReferralLetter(_Strict):
    sections: list[LetterSection]
    generated_from_snapshot: int


class Receipt(_Strict):
    canonical_json: str  # exact UTF-8 string that was hashed (floats excluded / stringified)
    sha256: str
    snapshot: int
    created_at: str


class WindowView(_Strict):
    label_es: str
    label_en: str
    minutes: int
    elapsed_min: int
    remaining_min: int


class OnsetInfo(_Strict):
    last_known_well_at: str | None
    quote: str | None
    windows: list[WindowView]


class SessionState(_Strict):
    session_id: str
    started_at: str
    epoch: int
    snapshot: int
    phase: Literal["live", "finalized"]
    muse_enabled: bool
    live_audio_allowed: bool
    turns: list[Turn]
    partial: str | None
    fields: dict[str, FieldState]
    questions: list[Question]
    confirmations: list[ConfirmationRequest]
    onset: OnsetInfo | None
    result: EngineResultView | None
    reasoning: ReasonerView | None
    letter: ReferralLetter | None
    receipt: Receipt | None
    errors: list[str]


FieldState.model_rebuild()
Conflict.model_rebuild()

# Models whose JSON Schema is sent to the Meta Model API as `response_format`.
MODEL_OUTPUT_MODELS: tuple[type[BaseModel], ...] = (
    ExtractorOut,
    AdvocateOut,
    VisionOut,
    PhrasingOut,
    ReasonerOut,
)


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema for `response_format={"type":"json_schema", ... "strict": true}`.

    Inlines `$defs` (no `$ref`), drops `title`/`default`, and asserts the strict
    rules: object root, `additionalProperties:false` and every property required
    on every object, no `oneOf`/`allOf`, depth ≤ 10.
    """
    raw = model.model_json_schema()
    defs: dict[str, Any] = raw.pop("$defs", {})

    def walk(node: Any, depth: int, seen: tuple[str, ...]) -> Any:
        if depth > 10:
            raise ValueError(f"{model.__name__}: schema deeper than 10")
        if isinstance(node, list):
            return [walk(n, depth, seen) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            if name in seen:
                raise ValueError(f"{model.__name__}: recursive schema via {name}")
            return walk(defs[name], depth, (*seen, name))
        for bad in ("oneOf", "allOf"):
            if bad in node:
                raise ValueError(f"{model.__name__}: {bad} not allowed in strict mode")
        out = {k: walk(v, depth + 1, seen) for k, v in node.items()
               if k not in ("title", "default", "description")}
        if out.get("type") == "object":
            props = out.get("properties", {})
            if out.get("additionalProperties") is not False:
                raise ValueError(f"{model.__name__}: object without additionalProperties:false")
            if set(out.get("required", [])) != set(props):
                raise ValueError(f"{model.__name__}: not every property is required")
        return out

    schema = walk(raw, 0, ())
    if schema.get("type") != "object":
        raise ValueError(f"{model.__name__}: strict root must be an object")
    return schema


__all__ = [
    "MODEL_OUTPUT_MODELS",
    "AdvocateItemOut",
    "AdvocateOut",
    "ConfirmationRequest",
    "Conflict",
    "DeltaOut",
    "DxView",
    "EngineResultView",
    "Evidence",
    "ExtractorOut",
    "FieldState",
    "FieldValue",
    "LetterSection",
    "LetterStatement",
    "OnsetInfo",
    "PhrasingOut",
    "Question",
    "ReasonerOut",
    "ReasonerView",
    "Receipt",
    "RedFlagHitView",
    "ReferralLetter",
    "SessionState",
    "Source",
    "Status",
    "Turn",
    "Urgency3",
    "VisionOut",
    "WindowView",
    "strict_json_schema",
]

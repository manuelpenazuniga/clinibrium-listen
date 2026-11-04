"""LLM egress builders (L9). Fail closed.

Every payload that leaves for a model is built here: redacted turns plus
catalog keys/values only. Any key outside `config/field_catalog.json` raises
`EgressError` instead of being sent.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from api.catalog import load_catalog
from api.listen.contracts import EngineResultView, FieldValue, Question, Turn
from api.listen.redact import redact
from api.muse.interfaces import (
    AdvocateCtx,
    ExtractCtx,
    GroundingChunkView,
    QuestionDraft,
    ReasonerCtx,
    VisionCtx,
)


class EgressError(ValueError):
    pass


def _keys_ok(keys: Iterable[str]) -> list[str]:
    allowed = set(load_catalog().keys)
    out = list(keys)
    bad = sorted(k for k in out if k not in allowed)
    if bad:
        raise EgressError(f"non-catalog keys in egress payload: {bad}")
    return out


def _values_ok(values: Mapping[str, FieldValue]) -> dict[str, FieldValue]:
    _keys_ok(values)
    return {k: (redact(v) if isinstance(v, str) else v) for k, v in values.items()}


def _turns_ok(turns: Sequence[Turn]) -> list[Turn]:
    return [t.model_copy(update={"text": redact(t.text)}) for t in turns]


def catalog_keys() -> list[str]:
    return list(load_catalog().keys)


def extract_ctx(turns: Sequence[Turn], new_turn: Turn, values: Mapping[str, FieldValue],
                pending: Question | None) -> ExtractCtx:
    if pending is not None:
        _keys_ok([pending.key])
    return ExtractCtx(turns=_turns_ok(turns), new_turn=_turns_ok([new_turn])[0],
                      catalog_keys=catalog_keys(), current_values=_values_ok(values),
                      pending_question=pending)


def advocate_ctx(turns: Sequence[Turn], values: Mapping[str, FieldValue],
                 result: EngineResultView | None) -> AdvocateCtx:
    return AdvocateCtx(turns=_turns_ok(turns), current_values=_values_ok(values),
                       catalog_keys=catalog_keys(), result=result)


def vision_ctx(document_id: str) -> VisionCtx:
    return VisionCtx(document_id=document_id, catalog_keys=catalog_keys())


def phrase_draft(draft: QuestionDraft) -> QuestionDraft:
    _keys_ok([draft.key])
    return draft


def reasoner_ctx(confirmed: Mapping[str, FieldValue], result: EngineResultView,
                 grounding: Sequence[GroundingChunkView]) -> ReasonerCtx:
    return ReasonerCtx(confirmed_values=_values_ok(confirmed), result=result,
                       grounding=list(grounding))


__all__ = ["EgressError", "advocate_ctx", "extract_ctx", "phrase_draft", "reasoner_ctx",
           "vision_ctx"]

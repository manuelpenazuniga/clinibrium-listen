"""Live extractor (muse-spark-1.3): one new redacted turn → `ExtractorOut` (SPECS §7).

Egress (L9): the payload carries only redacted turns, catalog keys and current
values; unknown keys fail closed. Output sanitation drops deltas whose key is
outside the allowlist or whose value is not in exactly one, correctly typed,
slot. Quote/value validation (E-quote, E-support, E-neg) stays in
api/listen/evidence.py.
"""
from __future__ import annotations

from typing import Any

from api.catalog import Catalog, CatalogField, load_catalog
from api.listen.contracts import DeltaOut, ExtractorOut, FieldValue
from api.muse.client import SPARK, MuseClient, MuseError, load_prompt
from api.muse.interfaces import ExtractCtx

CONTEXT_TURNS = 4  # previous turns sent as context


def check_keys(keys: list[str] | Any, catalog: Catalog | None = None) -> None:
    """Fail closed if any key is not in the field catalog (L9)."""
    known = set((catalog or load_catalog()).keys)
    unknown = sorted(set(keys) - known)
    if unknown:
        raise MuseError(f"egress blocked: unknown catalog keys {unknown}")


def key_spec(keys: list[str], catalog: Catalog | None = None) -> list[dict[str, Any]]:
    """Compact per-key spec (key, type, label, enum values) — no lexicons."""
    cat = catalog or load_catalog()
    out: list[dict[str, Any]] = []
    for k in keys:
        f = cat.get(k)
        item: dict[str, Any] = {"key": k, "type": f.type, "label": f.label_es}
        if f.enum_values:
            item["values"] = f.enum_values
        out.append(item)
    return out


def _slot_ok(f: CatalogField, vb: Any, vi: Any, ve: Any, vt: Any) -> bool:
    filled = [v is not None for v in (vb, vi, ve, vt)]
    if sum(filled) != 1:
        return False
    if f.type == "bool":
        return vb is not None
    if f.type == "int":
        return vi is not None
    if f.type == "enum":
        return ve is not None and ve in (f.enum_values or [])
    return vt is not None and bool(str(vt).strip())  # str / float


def sanitize_deltas(deltas: list[DeltaOut], allowed: list[str],
                    pending_id: str | None = None, pending_key: str | None = None,
                    catalog: Catalog | None = None) -> list[DeltaOut]:
    cat = catalog or load_catalog()
    allow = set(allowed)
    out: list[DeltaOut] = []
    for d in deltas:
        if d.key not in allow or not d.quote.strip():
            continue
        if not _slot_ok(cat.get(d.key), d.value_bool, d.value_int, d.value_enum, d.value_text):
            continue
        # A delta for the pending question's key answers it; ids are never trusted
        # from the model (replays may come from a session with other ids).
        qid = pending_id if (pending_id and d.key == pending_key) else None
        out.append(d.model_copy(update={
            "confidence_pct": max(0, min(100, d.confidence_pct)),
            "answers_question_id": qid,
        }))
    return out


def _values(values: dict[str, FieldValue]) -> dict[str, FieldValue]:
    return {k: values[k] for k in sorted(values)}


class LiveExtractor:
    def __init__(self, client: MuseClient) -> None:
        self.client = client

    async def extract(self, ctx: ExtractCtx) -> ExtractorOut:
        check_keys(ctx.catalog_keys)
        check_keys(list(ctx.current_values))
        q = ctx.pending_question
        if q is not None:
            check_keys([q.key])
        prev = [t.text for t in ctx.turns if t.turn_id != ctx.new_turn.turn_id][-CONTEXT_TURNS:]
        user = {
            "keys": key_spec(ctx.catalog_keys),
            "context_turns": prev,
            "current_values": _values(ctx.current_values),
            "pending_question": ({"id": q.id, "key": q.key, "text_es": q.text_es}
                                 if q else None),
            "new_turn": ctx.new_turn.text,
        }
        # Output is filtered by the allowlist afterwards, so the key omits it.
        key_inputs = {"new_turn": ctx.new_turn.text, "pending_key": q.key if q else None}
        # Replay only: a dictated turn spoken while a question is pending may have
        # been recorded without one; fall back to that recording. The pending
        # question is still applied by sanitize_deltas below.
        alt = [{"new_turn": ctx.new_turn.text, "pending_key": None}] if q else None
        out = await self.client.complete(
            role="extractor", model=SPARK, system=load_prompt("extractor"), user=user,
            out=ExtractorOut, key_inputs=key_inputs, prompt_name="extractor",
            alt_key_inputs=alt)
        return ExtractorOut(deltas=sanitize_deltas(
            out.deltas, ctx.catalog_keys, q.id if q else None, q.key if q else None))

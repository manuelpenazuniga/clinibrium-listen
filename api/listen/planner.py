"""Next-question planner (SPECS §7 planner.py, L6). Pure and deterministic.

Candidates: catalog keys with `askable=true` that are ABSENT from `fields`
and were never asked. For each candidate outcome we evaluate the state with
that outcome added as confirmed and score

    impact = 10·[urgency changes] + 4·[forced/blocked actions change]
           + 3·[top-1 dx changes] + 2·[a red flag would fire]

taking the max over outcomes. Ties → catalog order. Ask only if impact > 0,
one pending at a time, at most `MAX_QUESTIONS` per case unless a red flag
is active.

What-if basis: the planner evaluates the C ∪ P picture (every non-rejected
proposal treated as stated), because the question is about the next datum the
clinician should collect, not about trust. Under the strictly conservative
view nothing can move until the clinician confirms, so every question would
score the same. The resulting `Question` never changes urgency by itself.

Bedside procedures: a manoeuvre records several catalog keys at once, so its
outcomes are the combinations of its absent member keys and the question is
asked once, under the lead key. This is procedural metadata (which keys one
manoeuvre fills), not a clinical rule. Dix-Hallpike records the side
(`dix_hallpike`), the torsional component and fatigability.
"""
from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from adapter import EngineResult
from api.catalog import Catalog, CatalogField, load_catalog
from api.listen.contracts import FieldState, FieldValue, Question
from api.listen.policy import all_values, eval_values, urgency_rank
from api.muse.interfaces import QuestionDraft

MAX_QUESTIONS = 6

# lead key → member keys recorded by the same manoeuvre
PROCEDURES: dict[str, tuple[str, ...]] = {
    "dix_hallpike": ("dix_hallpike", "torsion_confirmed_by_clinician", "nystagmus_fatigable"),
}

W_URGENCY, W_ACTIONS, W_TOP1, W_RED_FLAG = 10, 4, 3, 2


@dataclass(frozen=True)
class Plan:
    key: str
    impact: int
    reason: str
    draft: QuestionDraft


def _outcome_values(f: CatalogField) -> list[FieldValue]:
    if f.type == "enum":
        return list(f.enum_values or [])
    if f.type == "bool":
        return [True, False]
    return []  # int / float / str: no finite outcome set → not plannable


def _top1(r: EngineResult) -> str | None:
    return r.differential_order[0] if r.differential_order else None


def _actions(r: EngineResult) -> tuple[frozenset[str], frozenset[str]]:
    return frozenset(a.value for a in r.forced_actions), r.blocked_actions


def _fmt(v: FieldValue) -> str:
    return {True: "sí", False: "no"}.get(v, str(v)) if isinstance(v, bool) else str(v)


def score(base: EngineResult, alt: EngineResult) -> tuple[int, str]:
    """Impact of moving from `base` to `alt` + a deterministic reason string."""
    impact = 0
    why: list[str] = []
    if urgency_rank(alt.urgency) != urgency_rank(base.urgency):
        impact += W_URGENCY
        why.append(f"→ {alt.urgency.value.capitalize()}")
    new_flags = sorted(set(alt.red_flag_ids) - set(base.red_flag_ids))
    if new_flags:
        impact += W_RED_FLAG
        why.append(f"({', '.join(new_flags)})")
    if _actions(alt) != _actions(base):
        impact += W_ACTIONS
        freed = sorted(base.blocked_actions - alt.blocked_actions)
        if freed:
            why.append(f"desbloquea {', '.join(a.capitalize() for a in freed)}")
        if "R-E2" in base.applied_rails and "R-E2" not in alt.applied_rails:
            why.append("resuelve incertidumbre R-E2")
        if not freed and not new_flags:
            why.append("cambia acciones")
    if _top1(alt) != _top1(base):
        impact += W_TOP1
        why.append(f"hipótesis principal → {_top1(alt) or 'ninguna'}")
    return impact, " ".join(why)


def _members(lead: str, catalog: Catalog, present: set[str], asked: set[str]) -> list[str]:
    keys = PROCEDURES.get(lead, (lead,))
    return [k for k in keys if k in catalog.keys and k not in present and k not in asked]


def plan(fields: Mapping[str, FieldState], questions: Sequence[Question],
         red_flag_active: bool, catalog: Catalog | None = None) -> Plan | None:
    """The single next question, or None. Same state → same plan (L6)."""
    catalog = catalog or load_catalog()
    if any(q.status == "pending" for q in questions):
        return None
    if len(questions) >= MAX_QUESTIONS and not red_flag_active:
        return None

    asked = {q.key for q in questions}
    for q in questions:  # a skipped manoeuvre is not re-asked finding by finding
        if q.status == "skipped":
            asked |= set(PROCEDURES.get(q.key, ()))
    present = set(fields)
    member_of = {m: lead for lead, ms in PROCEDURES.items() for m in ms if m != lead}
    base_vals = all_values(fields)
    base = eval_values(base_vals)

    best: Plan | None = None
    for f in catalog.fields:
        if not f.askable or f.key in present or f.key in asked:
            continue
        lead = member_of.get(f.key)
        if lead is not None and lead not in present and lead not in asked:
            continue  # asked as part of its procedure
        keys = _members(f.key, catalog, present, asked) if f.key in PROCEDURES else [f.key]
        spaces = [_outcome_values(catalog.get(k)) for k in keys]
        if not keys or any(not s for s in spaces):
            continue
        top: tuple[int, str, str] | None = None
        for combo in itertools.product(*spaces):
            impact, why = score(base, eval_values({**base_vals, **dict(zip(keys, combo,
                                                                           strict=True))}))
            if impact > 0 and (top is None or impact > top[0]):
                outcome = ", ".join(f"{k}={_fmt(v)}" for k, v in zip(keys, combo, strict=True))
                top = (impact, outcome, why)
        if top is not None and (best is None or top[0] > best.impact):
            reason = f"si {top[1]} {top[2]}".strip()
            best = Plan(key=f.key, impact=top[0], reason=reason, draft=_draft(f, reason))
    return best


def _draft(f: CatalogField, reason: str, qid: str = "") -> QuestionDraft:
    return QuestionDraft(id=qid, key=f.key, label_es=f.label_es, label_en=f.label_en,
                         enum_values=f.enum_values, enum_labels_es=f.enum_labels_es,
                         reason=reason)


def template_text(draft: QuestionDraft) -> tuple[str, str]:
    """Deterministic question text (used before / without the Phraser)."""
    if draft.enum_values:
        labels = draft.enum_labels_es or {}
        opts = ", ".join(labels.get(v, v).lower() for v in draft.enum_values)
        return (f"¿{draft.label_es}? ({opts})",
                f"{draft.label_en}? ({', '.join(draft.enum_values)})")
    return f"¿{draft.label_es}: presente o ausente?", f"{draft.label_en}: present or absent?"


def to_question(p: Plan, qid: str) -> Question:
    es, en = template_text(p.draft)
    return Question(id=qid, key=p.key, text_es=es, text_en=en, reason=p.reason,
                    impact=p.impact, status="pending")


def procedure_keys(key: str) -> tuple[str, ...]:
    return PROCEDURES.get(key, (key,))


def answered_by(question: Question, keys: Iterable[str]) -> bool:
    return any(k in procedure_keys(question.key) for k in keys)


__all__ = [
    "MAX_QUESTIONS",
    "PROCEDURES",
    "Plan",
    "answered_by",
    "plan",
    "procedure_keys",
    "score",
    "template_text",
    "to_question",
]

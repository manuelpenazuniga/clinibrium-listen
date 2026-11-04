"""Deterministic evidence validation (SPECS §6.1, L2).

- **E-quote:** a delta's quote must be a normalized substring of its source
  text (a final turn, or a document's `read_text`).
- **E-support:** the quote must contain a lexicon term for the key/value
  (catalog `lexicon`). For enums the term must belong to the proposed value.
- **E-neg:** a positive bool needs at least one NON-negated concept term; a
  term preceded by a negation cue within `negation_window_tokens` tokens (same
  clause), or followed by a postfix negation ("diplopía negativa"), can only
  yield `false`.
- **Short answers:** `sí/si/positivo` / `no/negativo` / `no lo evalué…` are
  classified before any model sees the turn.

Everything here is pure. Failures return a reason string (logged by the
session), never raise.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from api.catalog import Catalog, CatalogField, load_catalog, normalize
from api.listen.contracts import DeltaOut, FieldValue

_TOKEN = re.compile(r"[a-z0-9]+")
_CLAUSE_SPLIT = re.compile(r"[.;:,¿?¡!\n]+")
POSTFIX_NEGATIONS = frozenset({"negativo", "negativa", "ausente"})
# Tokens that end a negation's scope ("sin cefalea y con disartria").
NEGATION_BREAKERS = frozenset({"con", "pero"})


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))


def _find(toks: list[str], term: list[str]) -> list[int]:
    n = len(term)
    if n == 0:
        return []
    return [i for i in range(len(toks) - n + 1) if toks[i : i + n] == term]


# --------------------------------------------------------------------- E-quote


def quote_in(quote: str, sources: Iterable[str]) -> bool:
    """E-quote: normalized `quote` is a substring of one normalized source."""
    q = normalize(quote)
    if not q:
        return False
    return any(q in normalize(s) for s in sources)


# ------------------------------------------------------------ E-support / E-neg


def negated(toks: list[str], start: int, end: int, catalog: Catalog) -> bool:
    """Is the term at toks[start:end] negated (prefix cue within the window, or
    a postfix negation right after it)?"""
    cues = [tokens(c) for c in catalog.negation_cues]
    lo = start
    for back in range(1, catalog.negation_window_tokens + 1):
        i = start - back
        if i < 0 or toks[i] in NEGATION_BREAKERS:
            break
        lo = i
    before = toks[lo:start]
    if any(_find(before, cue) for cue in cues):
        return True
    return any(t in POSTFIX_NEGATIONS for t in toks[end : end + 2])


def _term_hits(clause_toks: list[str], terms: Iterable[str]) -> list[tuple[int, int]]:
    hits: list[tuple[int, int]] = []
    for term in terms:
        tt = tokens(term)
        hits += [(s, s + len(tt)) for s in _find(clause_toks, tt)]
    return hits


def _clauses(text: str) -> list[list[str]]:
    return [t for t in (tokens(c) for c in _CLAUSE_SPLIT.split(text)) if t]


def supports(field: CatalogField, value: FieldValue, quote: str,
             catalog: Catalog | None = None) -> str | None:
    """E-support + E-neg. Returns None if `quote` supports `value`, else a reason."""
    catalog = catalog or load_catalog()
    clauses = _clauses(quote)
    if field.type == "enum":
        terms = field.lexicon.get(str(value), [])
        if not any(_term_hits(c, terms) for c in clauses):
            return f"E-support: no lexicon term for {field.key}={value}"
        return None
    if field.type == "bool":
        concept = field.lexicon.get("*", [])
        false_only = field.lexicon.get("false", [])
        if value is True:
            for c in clauses:
                for s, e in _term_hits(c, concept):
                    if not negated(c, s, e, catalog):
                        return None
            if any(_term_hits(c, concept) for c in clauses):
                return f"E-neg: negated term cannot support {field.key}=true"
            return f"E-support: no lexicon term for {field.key}"
        if any(_term_hits(c, [*concept, *false_only]) for c in clauses):
            return None
        return f"E-support: no lexicon term for {field.key}"
    # int / float / str: a context term of the key must be present
    if any(_term_hits(c, field.lexicon.get("*", [])) for c in clauses):
        return None
    return f"E-support: no lexicon term for {field.key}"


# ------------------------------------------------------------- typed values


def delta_value(d: DeltaOut, field: CatalogField) -> FieldValue | None:
    """The single typed value of a delta, checked against the catalog type.
    Floats are stored as str with one fixed decimal (no floats in state)."""
    filled = [v for v in (d.value_bool, d.value_int, d.value_enum, d.value_text) if v is not None]
    if len(filled) != 1:
        return None
    if field.type == "bool":
        return d.value_bool if isinstance(d.value_bool, bool) else None
    if field.type == "int":
        v = d.value_int
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None
    if field.type == "enum":
        return d.value_enum if d.value_enum in (field.enum_values or []) else None
    if field.type == "float":
        raw = d.value_text if d.value_text is not None else d.value_int
        try:
            return f"{float(str(raw).replace(',', '.')):.1f}"
        except (TypeError, ValueError):
            return None
    if field.type == "str":
        return d.value_text.strip() if d.value_text and d.value_text.strip() else None
    return None


@dataclass(frozen=True)
class Accepted:
    key: str
    value: FieldValue
    quote: str
    confidence_pct: int
    answers_question_id: str | None


def validate_delta(d: DeltaOut, sources: list[str], catalog: Catalog | None = None,
                   ) -> Accepted | str:
    """Full gate for one model delta: catalog key, typed value, E-quote,
    E-support, E-neg. Returns `Accepted` or the drop reason."""
    catalog = catalog or load_catalog()
    try:
        field = catalog.get(d.key)
    except KeyError:
        return f"unknown key {d.key!r}"
    value = delta_value(d, field)
    if value is None:
        return f"bad value for {d.key}"
    if not quote_in(d.quote, sources):
        return f"E-quote: quote for {d.key} not found in source"
    reason = supports(field, value, d.quote, catalog)
    if reason is not None:
        return reason
    conf = min(100, max(0, int(d.confidence_pct)))
    return Accepted(d.key, value, d.quote, conf, d.answers_question_id)


# --------------------------------------------------------------- short answers

ShortAnswer = Literal["yes", "no", "skip"]

_SKIP = frozenset({
    "no lo evalue", "no lo evalué", "no evaluado", "no evaluada", "no se evaluo",
    "no lo evaluamos", "no se", "no lo se", "no realizado", "no realizada",
    "no lo hice", "no se hizo", "no lo examine",
})
_SKIP_NORM = frozenset(normalize(s) for s in _SKIP)
_YES = frozenset({"si", "positivo", "positiva", "presente"})
_NO = frozenset({"no", "negativo", "negativa", "ausente"})


def classify_short_answer(text: str) -> ShortAnswer | None:
    """Deterministic answer to a pending question, from the turn's FIRST
    clause only ("No, sin diplopía." → no; "No refiere diplopía" → None)."""
    parts = [c for c in _CLAUSE_SPLIT.split(text) if c.strip()]
    if not parts:
        return None
    first = " ".join(tokens(parts[0]))
    if first in _SKIP_NORM:
        return "skip"
    if first in _YES:
        return "yes"
    if first in _NO:
        return "no"
    return None


def short_answer_value(kind: ShortAnswer, field: CatalogField) -> FieldValue | None:
    """Value for the pending question's key, or None (→ ask the extractor)."""
    if kind == "skip":
        return None
    if field.type == "bool":
        return kind == "yes"
    if field.type == "enum" and kind == "no":
        for neg in ("negative", "none"):
            if neg in (field.enum_values or []):
                return neg
    return None


__all__ = [
    "Accepted",
    "ShortAnswer",
    "classify_short_answer",
    "delta_value",
    "negated",
    "quote_in",
    "short_answer_value",
    "supports",
    "tokens",
    "validate_delta",
]

"""Keyword baseline extractor (no model) — the bench's point of comparison.

Deliberately simple, the way a regex-based NLP pipeline would be built:
- split each turn into sentences on `. ; ! ?` (commas do NOT split);
- match catalog-lexicon terms on normalized tokens (lowercase, no accents);
- bool: a term preceded by a negation cue within `negation_window_tokens`
  tokens (same sentence) → False; a term in the lexicon's `false` bucket → False;
- enum: the longest matching term in the sentence wins (first by catalog order on ties);
- int: `NN años` for age, `N episodios/crisis/veces` for counts; time since
  onset from `hace N horas|minutos|días`;
- str (medications): the rest of a sentence starting with `toma|usa`;
- later sentences overwrite earlier ones for the same key.

No clause-level scoping, no "con/pero" negation breakers, no within-sentence
corrections: those are exactly the cases where a language model should help.
"""
from __future__ import annotations

import re

from api.catalog import Catalog, CatalogField, load_catalog, normalize
from bench.common import Fields, FieldValue

_SENTENCE = re.compile(r"[.;!?¡¿\n]+")
_TOKEN = re.compile(r"[a-z0-9]+")
_WORDS: dict[str, int] = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "doce": 12, "veinte": 20,
}
_NUM = r"(\d+|" + "|".join(_WORDS) + r")"
_AGE = re.compile(r"\b(\d{1,3})\s+anos\b")
_COUNT = re.compile(r"\b" + _NUM + r"\s+(?:episodios|crisis|veces)\b")
_SINCE = re.compile(r"\bhace\s+" + _NUM + r"\s+(horas?|minutos?|dias?)\b")
_MEDS = re.compile(r"\b(?:toma|usa)\s+(.+)$", re.IGNORECASE)
_FLOAT = re.compile(r"(\d+(?:[.,]\d+)?)")


def _num(s: str) -> int:
    return int(s) if s.isdigit() else _WORDS[s]


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))


def _find(tokens: list[str], term: list[str]) -> list[int]:
    n = len(term)
    return [i for i in range(len(tokens) - n + 1) if tokens[i : i + n] == term]


def _match(f: CatalogField, sentence: str, cat: Catalog,
           cues: list[list[str]]) -> FieldValue | None:
    norm = normalize(sentence)
    toks = _tokens(sentence)
    if f.key == "age_years":
        m = _AGE.search(norm)
        return int(m.group(1)) if m else None
    if f.key == "episode_count":
        m = _COUNT.search(norm)
        return _num(m.group(1)) if m else None
    if f.key == "context.last_known_well_minutes_ago":
        m = _SINCE.search(norm)
        if not m:
            return None
        unit = m.group(2)
        return _num(m.group(1)) * (60 if unit.startswith("h") else 1440 if unit.startswith("d")
                                   else 1)
    if f.type == "str":
        m = _MEDS.search(sentence.strip())
        return m.group(1).strip() if m else None

    hits: list[tuple[int, int, str]] = []  # (start, length, bucket)
    for bucket, terms in f.lexicon.items():
        for term in terms:
            tt = _tokens(term)
            if tt:
                hits += [(s, len(tt), bucket) for s in _find(toks, tt)]
    if not hits:
        return None

    if f.type == "enum":
        return max(hits, key=lambda h: h[1])[2]  # longest term; first on ties
    if f.type == "bool":
        if any(b == "false" for _, _, b in hits):
            return False
        start = min(s for s, _, _ in hits)
        before = toks[max(0, start - cat.negation_window_tokens) : start]
        return not any(_find(before, cue) for cue in cues)
    if f.type == "float":
        m = _FLOAT.search(norm)  # first number in the sentence
        return f"{float(m.group(1).replace(',', '.')):.1f}" if m else None
    return None  # other ints: no generic rule in the baseline


def extract(text: str, catalog: Catalog | None = None) -> Fields:
    """Atomic field values stated in `text` (later sentences win)."""
    cat = catalog or load_catalog()
    cues = [_tokens(c) for c in cat.negation_cues]
    out: Fields = {}
    for sentence in (s for s in _SENTENCE.split(text) if s.strip()):
        for f in cat.fields:
            v = _match(f, sentence, cat, cues)
            if v is not None:
                out[f.key] = v
    return out


__all__ = ["extract"]

"""Spoken Spanish and English numbers → ints (deterministic, pure).

The realtime ASR writes numbers as words ("paciente de sesenta y ocho años,
vértigo hace doce horas"). This module parses them, over the normalized
tokens of `api.listen.evidence.tokens` (lowercase, accents stripped), so the
mock extractor and the evidence gate treat "sesenta y ocho" exactly like "68".

Covers 0–999 in words ("cero" … "novecientos noventa y nueve", "veintidós",
"dieciséis", "ciento veinte"; "zero" … "nine hundred ninety-nine", "sixty-eight",
"one hundred and twenty") and plain digit tokens. No clinical logic.

English "one" is deliberately parsed but "a"/"an" are not ("an hour ago" states
no number). "once" stays Spanish 11, as before.
"""
from __future__ import annotations

from collections.abc import Sequence

UNITS: dict[str, int] = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
}
TEENS: dict[str, int] = {
    "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
    "veintiun": 21, "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27,
    "veintiocho": 28, "veintinueve": 29,
}
TENS: dict[str, int] = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
    "ochenta": 80, "noventa": 90,
}
HUNDREDS: dict[str, int] = {
    "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200, "trescientos": 300,
    "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400, "quinientos": 500,
    "quinientas": 500, "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
    "setecientas": 700, "ochocientos": 800, "ochocientas": 800, "novecientos": 900,
    "novecientas": 900,
}
UNITS_EN: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9,
}
TEENS_EN: dict[str, int] = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS_EN: dict[str, int] = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
NUMBER_WORDS = frozenset({*UNITS, *TEENS, *TENS, *HUNDREDS, *UNITS_EN, *TEENS_EN, *TENS_EN,
                          "hundred"})

# time units after "hace N …" → minutes (for context.last_known_well_minutes_ago)
UNIT_MINUTES: dict[str, int] = {
    "min": 1, "minuto": 1, "minutos": 1, "h": 60, "hr": 60, "hrs": 60, "hora": 60,
    "horas": 60, "dia": 1440, "dias": 1440, "semana": 10080, "semanas": 10080,
    "mins": 1, "minute": 1, "minutes": 1, "hour": 60, "hours": 60, "day": 1440, "days": 1440,
    "week": 10080, "weeks": 10080,
}


def _below_100(toks: Sequence[str], i: int) -> tuple[int, int] | None:
    if i >= len(toks):
        return None
    t = toks[i]
    if t in TEENS:
        return TEENS[t], i + 1
    if t in TENS:
        value, end = TENS[t], i + 1
        if (end + 1 < len(toks) and toks[end] == "y" and toks[end + 1] in UNITS
                and toks[end + 1] != "cero"):
            return value + UNITS[toks[end + 1]], end + 2
        return value, end
    if t in UNITS:
        return UNITS[t], i + 1
    return None


def _below_100_en(toks: Sequence[str], i: int) -> tuple[int, int] | None:
    """"sixty eight" ("sixty-eight" tokenizes to two words), "twelve", "seven"."""
    if i >= len(toks):
        return None
    t = toks[i]
    if t in TEENS_EN:
        return TEENS_EN[t], i + 1
    if t in TENS_EN:
        value, end = TENS_EN[t], i + 1
        if end < len(toks) and toks[end] in UNITS_EN and toks[end] != "zero":
            return value + UNITS_EN[toks[end]], end + 1
        return value, end
    if t in UNITS_EN:
        return UNITS_EN[t], i + 1
    return None


def _parse_en(toks: Sequence[str], i: int) -> tuple[int, int] | None:
    head = _below_100_en(toks, i)
    if head is None:
        return None
    value, end = head
    # "one hundred [and] twenty"
    if value < 10 and end < len(toks) and toks[end] == "hundred":
        value, end = value * 100, end + 1
        j = end + 1 if end < len(toks) and toks[end] == "and" else end
        rest = _below_100_en(toks, j)
        if rest is not None:
            return value + rest[0], rest[1]
    return value, end


def parse_at(toks: Sequence[str], i: int) -> tuple[int, int] | None:
    """The number starting at token `i` → (value, end index), or None."""
    if i >= len(toks):
        return None
    t = toks[i]
    if t.isdigit():
        return int(t), i + 1
    en = _parse_en(toks, i)
    if en is not None:
        return en
    if t in HUNDREDS:
        value, end = HUNDREDS[t], i + 1
        rest = _below_100(toks, end) if t != "cien" else None
        if rest is not None:
            return value + rest[0], rest[1]
        return value, end
    return _below_100(toks, i)


def number_ending_at(toks: Sequence[str], end: int, max_words: int = 4,
                     ) -> tuple[int, int] | None:
    """The longest number phrase that ends exactly at `end` (exclusive) →
    (value, start index), e.g. "sesenta y ocho | años" → (68, start of "sesenta")."""
    for start in range(max(0, end - max_words), end):
        hit = parse_at(toks, start)
        if hit is not None and hit[1] == end:
            return hit[0], start
    return None


def numbers_in(toks: Sequence[str]) -> list[tuple[int, int, int]]:
    """Every maximal number phrase → (value, start, end)."""
    out: list[tuple[int, int, int]] = []
    i = 0
    while i < len(toks):
        hit = parse_at(toks, i)
        if hit is None:
            i += 1
            continue
        out.append((hit[0], i, hit[1]))
        i = hit[1]
    return out


def minutes_ago(toks: Sequence[str]) -> int | None:
    """`hace <número> <unidad>` or `<number> <unit> ago` → minutes ("hace doce
    horas", "twelve hours ago" → 720), else None."""
    for i, t in enumerate(toks):
        if t != "hace":
            continue
        hit = parse_at(toks, i + 1)
        if hit is None or hit[1] >= len(toks):
            continue
        factor = UNIT_MINUTES.get(toks[hit[1]])
        if factor is not None:
            return hit[0] * factor
    for value, _, end in numbers_in(toks):
        if end + 1 < len(toks) and toks[end + 1] == "ago":
            factor = UNIT_MINUTES.get(toks[end])
            if factor is not None:
                return value * factor
    return None


__all__ = ["NUMBER_WORDS", "UNIT_MINUTES", "minutes_ago", "number_ending_at", "numbers_in",
           "parse_at"]

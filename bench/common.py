"""Shared bench helpers: case loading, atomic-field projection, engine evaluation.

Pure and offline. The projection follows SPECS §5.1 (`policy.project`); it is
re-implemented here because `api/listen/policy.py` is owned by workstream 1A and
the bench must run on its own.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "engine"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapter import EngineResult, evaluate  # noqa: E402
from api.catalog import load_catalog, normalize  # noqa: E402
from clinibrium.contracts.enums import Urgency  # noqa: E402
from clinibrium.contracts.features import SET_FIELDS, CaseFeatures  # noqa: E402
from clinibrium.rails.ordering import urgency_max  # noqa: E402

CASES_DIR = ROOT / "bench" / "cases"
RESULTS_DIR = ROOT / "bench" / "results"

FieldValue = bool | int | str
Fields = dict[str, FieldValue]

CASE_KEYS = {"id", "title_es", "title_en", "turns", "answers", "documents", "gold"}
TURN_KEYS = {"turn_id", "start_ms", "end_ms", "text"}
DOC_KEYS = {"id", "kind", "text"}
GOLD_KEYS = {"fields", "urgency", "top1_dx", "first_question_key"}


def case_paths() -> list[Path]:
    return sorted(CASES_DIR.glob("*.json"))


def load_cases() -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in case_paths()]


def project(fields: Fields) -> CaseFeatures:
    """Atomic fields → `CaseFeatures` (SPECS §5.1).

    Scalar key → its value; set item key → member iff `True`; `context.*` keys
    are not engine features; absent → engine default. Floats arrive as strings.
    """
    catalog = load_catalog()
    scalars: dict[str, Any] = {}
    sets: dict[str, set[str]] = {name: set() for name in SET_FIELDS}
    for key, value in fields.items():
        if key.startswith("context."):
            continue
        head, _, item = key.partition(".")
        if item and head in SET_FIELDS:
            if value is True:
                sets[head].add(item)
            continue
        if catalog.get(key).type == "float":
            scalars[key] = float(value)
        else:
            scalars[key] = value
    return CaseFeatures(**scalars, **sets)


def evaluate_fields(fields: Fields) -> EngineResult:
    return evaluate(project(fields))


def top1(result: EngineResult) -> str | None:
    order = result.differential_order
    return order[0] if order else None


def under_triage(predicted: Urgency, gold: Urgency) -> bool:
    """`predicted` is strictly less urgent than `gold` (rank-table comparison, §0.7)."""
    return predicted != gold and urgency_max(predicted, gold) == gold


def values_equal(key: str, a: FieldValue | None, b: FieldValue | None) -> bool:
    """Type-strict equality (`True != 1`); str compared normalized, floats numerically."""
    if a is None or b is None:
        return a is b
    if type(a) is not type(b):
        return False
    ftype = load_catalog().get(key).type
    if ftype == "float":
        return float(str(a)) == float(str(b))
    if ftype == "str":
        return normalize(str(a)) == normalize(str(b))
    return a == b


def is_negative_gold(key: str, value: FieldValue) -> bool:
    """A gold value that records an assessed-and-absent finding."""
    if value is False:
        return True
    return load_catalog().get(key).type == "enum" and value in {"none", "negative"}


def check_value(key: str, value: object) -> str | None:
    """Validation error for `value` under `key`'s catalog type, or None."""
    try:
        f = load_catalog().get(key)
    except KeyError:
        return f"unknown key {key!r}"
    if f.type == "bool" and not isinstance(value, bool):
        return f"{key}: expected bool"
    if f.type == "int" and (isinstance(value, bool) or not isinstance(value, int)):
        return f"{key}: expected int"
    if f.type in {"str", "float"} and not isinstance(value, str):
        return f"{key}: expected str"
    if f.type == "enum" and value not in (f.enum_values or []):
        return f"{key}: {value!r} not in enum"
    return None


__all__ = [
    "CASES_DIR", "CASE_KEYS", "DOC_KEYS", "GOLD_KEYS", "RESULTS_DIR", "ROOT", "TURN_KEYS",
    "FieldValue", "Fields", "Urgency", "case_paths", "check_value", "evaluate_fields",
    "is_negative_gold", "load_cases", "project", "top1", "under_triage", "values_equal",
]

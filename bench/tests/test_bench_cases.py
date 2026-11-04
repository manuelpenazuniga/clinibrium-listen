"""Every bench case has the demo-case shape, valid gold, and A/B equal the built-ins."""
from __future__ import annotations

from typing import Any

import pytest

from api.catalog import load_catalog
from api.demo_cases import BUILTIN_DEMO_CASES, load_demo_cases
from bench.common import (
    CASE_KEYS,
    DOC_KEYS,
    GOLD_KEYS,
    TURN_KEYS,
    check_value,
    evaluate_fields,
    load_cases,
    top1,
)

CASES = load_cases()
URGENCIES = {"inmediata", "prioritaria", "ambulatoria"}


def test_enough_cases_unique_ids() -> None:
    ids = [c["id"] for c in CASES]
    assert len(CASES) >= 8
    assert len(set(ids)) == len(ids)
    assert ids[:2] == ["A", "B"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_shape(case: dict[str, Any]) -> None:
    assert set(case) == CASE_KEYS
    assert isinstance(case["title_es"], str) and isinstance(case["title_en"], str)
    assert case["turns"], "a case needs dictation"
    prev_end, prev_id = -1, 0
    for t in case["turns"]:
        assert set(t) == TURN_KEYS
        assert isinstance(t["text"], str) and t["text"].strip()
        assert t["turn_id"] == prev_id + 1
        assert prev_end < t["start_ms"] < t["end_ms"]
        prev_end, prev_id = t["end_ms"], t["turn_id"]
    keys = set(load_catalog().keys)
    assert all(k in keys and isinstance(v, str) for k, v in case["answers"].items())
    for d in case["documents"]:
        assert set(d) == DOC_KEYS


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_gold_valid_and_consistent_with_engine(case: dict[str, Any]) -> None:
    gold = case["gold"]
    assert set(gold) == GOLD_KEYS
    assert gold["fields"]
    for key, value in gold["fields"].items():
        assert check_value(key, value) is None, (key, value)
    assert gold["urgency"] in URGENCIES
    r = evaluate_fields(gold["fields"])
    assert r.urgency.value == gold["urgency"], "stale gold urgency: run bench/gold.py --write"
    if gold["top1_dx"] is not None:
        assert top1(r) == gold["top1_dx"]
    fq = gold["first_question_key"]
    assert fq is None or load_catalog().get(fq).askable


@pytest.mark.parametrize("builtin", BUILTIN_DEMO_CASES, ids=lambda c: c["id"])
def test_demo_cases_equal_builtins(builtin: dict[str, Any]) -> None:
    case = next(c for c in CASES if c["id"] == builtin["id"])
    assert case == builtin


def test_api_serves_bench_cases() -> None:
    assert load_demo_cases() == CASES


def test_required_case_mix() -> None:
    """SPECS §7 bench: central red flags buried in ≥ 3 cases; benign BPPV ≥ 2."""
    inmediata = [c for c in CASES if c["gold"]["urgency"] == "inmediata"]
    bppv = [c for c in CASES if c["gold"]["top1_dx"] == "bppv_posterior"]
    assert len(inmediata) >= 3 and len(bppv) >= 2
    assert any(c["gold"]["fields"].get("presyncope_syncope") is True for c in CASES)
    negations = max(sum(v is False for v in c["gold"]["fields"].values()) for c in CASES)
    assert negations >= 8

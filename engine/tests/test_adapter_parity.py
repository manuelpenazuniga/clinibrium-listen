"""Parity: `adapter.evaluate` == `counterfactual.engine._deterministic_seal`.

Cases: the source repo's demo/tutorial presets (frontend/lib/presets.ts), the 20
bench dev cases, and arbitrary cases from the S0 property strategy. Compared on
urgency, forced actions and rails (against `_deterministic_seal` itself) and on
red flags and differential order (against the engines the seal feeds).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given

from adapter import EngineResult, evaluate
from clinibrium.contracts.enums import ForcedAction, Urgency
from clinibrium.contracts.features import CaseFeatures
from clinibrium.counterfactual.engine import _deterministic_seal
from clinibrium.differential_engine import evaluate as differential_evaluate
from clinibrium.redflag_engine import evaluate as redflag_evaluate
from tests.test_s0_properties import PROPERTY_SETTINGS, case_features

_FIX = Path(__file__).resolve().parent / "fixtures"


def _demo_cases() -> list[tuple[str, CaseFeatures]]:
    presets = json.loads((_FIX / "demo_presets.json").read_text())["cases"]
    out = [(p["id"], CaseFeatures.model_validate(p["features"])) for p in presets]
    for p in sorted((_FIX / "bench_dev").glob("*.json")):
        raw = json.loads(p.read_text())
        out.append((raw["id"], CaseFeatures.model_validate(raw["features"])))
    return out


DEMO_CASES = _demo_cases()


def _assert_parity(f: CaseFeatures) -> EngineResult:
    got = evaluate(f)
    urgency, forced, rails = _deterministic_seal(f)
    assert got.urgency == urgency
    assert {a.value for a in got.forced_actions} == forced
    assert list(got.applied_rails) == rails
    rf = redflag_evaluate(f)
    assert got.red_flag == rf
    assert got.red_flag_ids == tuple(h.id for h in rf.hits)
    dx = differential_evaluate(f)
    assert got.differential == dx
    assert got.differential_order == tuple(c.diagnosis.value for c in dx.candidates)
    return got


def test_demo_cases_loaded() -> None:
    assert len(DEMO_CASES) == 23  # 3 presets + 20 bench dev cases


@pytest.mark.parametrize(("case_id", "features"), DEMO_CASES, ids=[c[0] for c in DEMO_CASES])
def test_adapter_matches_deterministic_seal_on_demo_cases(
    case_id: str, features: CaseFeatures
) -> None:
    _assert_parity(features)


@PROPERTY_SETTINGS
@given(case_features())
def test_adapter_matches_deterministic_seal_on_arbitrary_cases(f: CaseFeatures) -> None:
    _assert_parity(f)


def test_preset_anchors() -> None:
    """Sanity anchors on the tutorial presets (values the source UI demoes)."""
    by_id = dict(DEMO_CASES)
    bppv = evaluate(by_id["bppv-benign"])
    assert bppv.urgency == Urgency.ambulatoria
    assert "EPLEY" not in bppv.blocked_actions
    stroke = evaluate(by_id["stroke-hints"])
    assert stroke.urgency == Urgency.inmediata
    assert ForcedAction.DERIVAR_URGENTE in stroke.forced_actions
    assert stroke.red_flag.red_flag_activa


def test_evaluate_is_pure_and_deterministic() -> None:
    for _id, f in DEMO_CASES:
        before = f.model_dump()
        assert evaluate(f) == evaluate(f)
        assert f.model_dump() == before

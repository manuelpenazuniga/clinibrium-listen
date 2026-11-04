"""Keyword baseline, runner policy bits, mock end-to-end, live/replay guards."""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from bench import baseline
from bench.common import load_cases
from bench.run import (
    NetworkBlocked,
    network_blocked,
    planned_model_calls,
    run,
    short_answer,
)


@pytest.mark.parametrize("text", ["sin diplopía", "Niega diplopía.", "no refiere visión doble"])
def test_baseline_negation_never_true(text: str) -> None:
    assert baseline.extract(text)["focal_signs.diplopia"] is False


def test_baseline_basic_fields() -> None:
    got = baseline.extract("Paciente de 68 años, hipertenso, vértigo continuo hace 12 horas.")
    assert got["age_years"] == 68
    assert got["vascular_risk_factors.hypertension"] is True
    assert got["timing_pattern"] == "acute_continuous"
    assert got["context.last_known_well_minutes_ago"] == 720


def test_baseline_later_sentence_wins() -> None:
    got = baseline.extract("Dix-Hallpike positivo derecho. Corrijo: positivo izquierdo.")
    assert got["dix_hallpike"] == "left_positive"


@pytest.mark.parametrize(("text", "want"), [
    ("Sí.", "true"), ("no", "false"), ("Negativo.", "false"), ("No lo evalué.", "skip"),
    ("no sé", "skip"), ("Positivo derecho, torsional.", None),
])
def test_short_answer(text: str, want: str | None) -> None:
    assert short_answer(text) == want


def test_network_blocked_restores() -> None:
    with network_blocked():
        with pytest.raises(NetworkBlocked):
            socket.create_connection(("127.0.0.1", 9))
        with socket.socket() as s, pytest.raises(NetworkBlocked):
            s.connect(("127.0.0.1", 9))
    with socket.socket() as s:  # restored: a real (refused) connection attempt, not ours
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", 9))
        except NetworkBlocked:
            pytest.fail("network guard leaked out of its context")
        except OSError:
            pass


async def test_mock_run_end_to_end(tmp_path: Path) -> None:
    report = await run("mock", out_dir=tmp_path)
    assert report["n_cases"] == len(load_cases())
    for name in ("mock.json", "table.md", "table.json"):
        assert (tmp_path / name).is_file()
    table = json.loads((tmp_path / "table.json").read_text())
    assert {r["metric"] for r in table["summary"]} >= {
        "key_accuracy", "red_flag_recall", "negation_accuracy", "urgency_agreement",
        "latency_ms_mean", "cost_usd"}
    by_id = {c["id"]: c for c in report["cases"]}
    # Demo cases: the mock extractor reaches the gold urgency on both.
    assert by_id["A"]["systems"]["muse"]["urgency"] == "ambulatoria"
    assert by_id["B"]["systems"]["muse"]["urgency"] == "inmediata"
    # Scripted short answers: "No lo evalué." leaves the key absent (not assessed).
    assert "skew_deviation" not in by_id["L"]["systems"]["muse"]["predicted_fields"]
    assert by_id["L"]["systems"]["muse"]["predicted_fields"]["focal_signs.diplopia"] is False
    assert report["systems"]["muse"]["calls"] == report["planned_calls"]


async def test_live_refuses_without_budget(monkeypatch: pytest.MonkeyPatch,
                                           tmp_path: Path) -> None:
    monkeypatch.delenv("MUSE_MAX_LIVE_CALLS", raising=False)
    with pytest.raises(SystemExit, match="refusing --mode live"):
        await run("live", out_dir=tmp_path)
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "1")
    with pytest.raises(SystemExit, match="refusing --mode live"):
        await run("live", out_dir=tmp_path)
    assert not any(tmp_path.iterdir())


def test_planned_calls_skip_short_bool_answers() -> None:
    case = next(c for c in load_cases() if c["id"] == "L")
    assert planned_model_calls([case]) == len(case["turns"])

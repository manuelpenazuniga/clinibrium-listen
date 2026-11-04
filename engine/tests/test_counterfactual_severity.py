"""Plan F — the counterfactual's severity scale vs the rails' urgency rank."""
from __future__ import annotations

import dataclasses
import itertools
import json
import subprocess
from pathlib import Path

from clinibrium.contracts.enums import Urgency
from clinibrium.contracts.features import CaseFeatures
from clinibrium.counterfactual.engine import _SEVERITY, analyze
from clinibrium.rails.ordering import _URGENCY_RANK

# Port note: paths are anchored to this file (the source ran from backend/), and
# the 20 bench dev cases are vendored in fixtures/bench_dev/ (the source loaded
# them via bench.schema.load_set("dev"); bench/ is not part of the engine port).
_HERE = Path(__file__).resolve().parent
_ENGINE = _HERE.parent
SNAPSHOT = json.loads((_HERE / "fixtures" / "counterfactual_snapshot.json").read_text())


@dataclasses.dataclass(frozen=True)
class _DevCase:
    id: str
    features: CaseFeatures


def load_set(name: str) -> list[_DevCase]:
    assert name == "dev"
    out = []
    for p in sorted((_HERE / "fixtures" / "bench_dev").glob("*.json")):
        raw = json.loads(p.read_text())
        out.append(_DevCase(raw["id"], CaseFeatures.model_validate(raw["features"])))
    return out


def test_severity_is_the_exact_inverse_of_the_rails_rank() -> None:
    for a, b in itertools.product(Urgency, Urgency):
        assert (_SEVERITY[a] > _SEVERITY[b]) == (_URGENCY_RANK[a] < _URGENCY_RANK[b])


def test_counterfactual_output_unchanged_by_the_rename() -> None:
    """Snapshot taken before the rename over the 20 bench dev cases."""
    got = json.loads(json.dumps(
        {c.id: dataclasses.asdict(analyze(c.features)) for c in load_set("dev")}, default=str))
    assert got == SNAPSHOT


def test_old_name_is_gone_from_the_counterfactual() -> None:
    """No code use of the old name in the counterfactual (the comment explaining
    the rename may mention it), and nothing in the backend imports it from there."""
    uses = subprocess.run(
        ["grep", "-rnE", r"_URGENCY_RANK(\[|:| =)", "clinibrium/counterfactual"],
        capture_output=True, text=True, cwd=_ENGINE,
    )
    assert uses.returncode == 1 and uses.stdout == ""  # 1 = searched, no match (2 = error)
    imports = subprocess.run(
        ["grep", "-rnE", r"counterfactual(\.engine)? import .*_URGENCY_RANK", "clinibrium",
         "tests"],
        capture_output=True, text=True, cwd=_ENGINE,
    )
    assert imports.returncode == 1 and imports.stdout == ""

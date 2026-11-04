"""config/field_catalog.json is fresh and consistent with the engine contract."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from api.catalog import load_catalog
from clinibrium.contracts.features import SET_FIELDS, CaseFeatures

ROOT = Path(__file__).resolve().parents[2]


def test_catalog_is_up_to_date() -> None:
    r = subprocess.run([sys.executable, "scripts/gen_catalog.py", "--check"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_catalog_covers_every_case_feature_atomically() -> None:
    keys = set(load_catalog().keys)
    for name in CaseFeatures.model_fields:
        if name in SET_FIELDS:
            assert not any(k == name for k in keys)
            assert any(k.startswith(f"{name}.") for k in keys), name
        else:
            assert name in keys, name
    assert {"context.last_known_well_minutes_ago", "context.anticoagulated",
            "context.prior_stroke_tia", "context.medications"} <= keys


def test_catalog_entries_are_well_formed() -> None:
    cat = load_catalog()
    groups = {g["id"] for g in cat.groups}
    assert len(cat.keys) == len(set(cat.keys))
    for f in cat.fields:
        assert f.group in groups and f.label_es and f.label_en
        if f.type == "enum":
            assert f.enum_values and "not_done" not in f.enum_values
            assert set(f.lexicon) == set(f.enum_values)
        else:
            assert f.lexicon.get("*"), f.key

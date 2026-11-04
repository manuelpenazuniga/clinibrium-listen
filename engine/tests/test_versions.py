"""Plan J — clinical versioning per evaluation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from clinibrium import versions as v

MANIFEST = json.loads((Path(v.__file__).parent / "versions_manifest.json").read_text())
HOW = ("a clinical change needs a NEW version: bump {const} in clinibrium/versions.py and ADD "
       "the pair to clinibrium/versions_manifest.json (never edit an existing entry)")


def _check(kind: str, version: str, fingerprint: str) -> None:
    approved = MANIFEST[kind]
    assert fingerprint != v.UNAVAILABLE, "source not available to fingerprint"
    assert version in approved, f"{kind} {version!r} not approved; " + HOW.format(const=kind)
    assert approved[version] == fingerprint, (
        f"{kind} content changed (fingerprint {fingerprint}) but version {version!r} is "
        f"approved for {approved[version]}; " + HOW.format(const=kind))


def test_current_ruleset_is_an_approved_pair() -> None:
    _check("ruleset", v.RULESET_VERSION, v.ruleset_fingerprint())


def test_current_features_schema_is_an_approved_pair() -> None:
    _check("features_schema", v.FEATURES_SCHEMA_VERSION, v.features_schema_fingerprint())


def test_current_grounding_is_an_approved_pair() -> None:
    """Plan T1: the inline corpus the evaluation path uses is versioned too."""
    _check("grounding", v.GROUNDING_VERSION, v.grounding_fingerprint())


def test_manifest_never_reuses_a_fingerprint_for_two_versions() -> None:
    for kind in ("ruleset", "features_schema", "grounding"):
        fps = list(MANIFEST[kind].values())
        assert len(fps) == len(set(fps)), f"two {kind} versions share one fingerprint"


def test_fingerprints_are_stable_across_processes() -> None:
    code = ("from clinibrium import versions as v;"
            "print(v.ruleset_fingerprint(), v.features_schema_fingerprint(),"
            " v.grounding_fingerprint())")
    outs = {subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True,
                           env={"PYTHONHASHSEED": str(seed), "PATH": "/usr/bin:/bin"},
                           cwd=Path(__file__).resolve().parents[1]).stdout
            for seed in (1, 2, 3)}
    assert len(outs) == 1 and outs.pop().strip()


@pytest.mark.parametrize(("module", "find", "replace"), [
    ("clinibrium.rails.thresholds", None, "\n# changed threshold\n"),
    ("clinibrium.redflag_engine.rules", None, "\n# changed label\n"),
    ("clinibrium.contracts.features", None, "\n# changed validator\n"),
])
def test_any_change_to_the_engines_or_features_changes_a_fingerprint(
        monkeypatch, module, find, replace) -> None:
    """Mutation: a change in a rule table, a threshold or a CaseFeatures
    validator (even one that keeps the JSON schema) moves a fingerprint."""
    import importlib
    import inspect

    before = (v.ruleset_fingerprint(), v.features_schema_fingerprint())
    mod = importlib.import_module(module)
    real = inspect.getsource

    def patched(obj):
        src = real(obj)
        return src + replace if obj is mod else src

    monkeypatch.setattr(v.inspect, "getsource", patched)
    v.ruleset_fingerprint.cache_clear()
    v.features_schema_fingerprint.cache_clear()
    try:
        after = (v.ruleset_fingerprint(), v.features_schema_fingerprint())
    finally:
        monkeypatch.undo()
        v.ruleset_fingerprint.cache_clear()
        v.features_schema_fingerprint.cache_clear()
    assert after != before


def test_any_change_to_the_inline_corpus_changes_the_grounding_fingerprint(monkeypatch) -> None:
    """Plan T1 mutation: editing a corpus chunk or the selection logic moves it."""
    import inspect

    from clinibrium.grounding import inline

    before = v.grounding_fingerprint()
    real = inspect.getsource

    def patched(obj):
        src = real(obj)
        return src + "\n# reworded chunk\n" if obj is inline else src

    monkeypatch.setattr(v.inspect, "getsource", patched)
    v.grounding_fingerprint.cache_clear()
    try:
        after = v.grounding_fingerprint()
    finally:
        monkeypatch.undo()
        v.grounding_fingerprint.cache_clear()
    assert after != before


def test_unavailable_source_never_raises(monkeypatch) -> None:
    def no_source(_obj):
        raise OSError("no source")

    monkeypatch.setattr(v.inspect, "getsource", no_source)
    v.ruleset_fingerprint.cache_clear()
    v.features_schema_fingerprint.cache_clear()
    try:
        assert v.ruleset_fingerprint() == v.UNAVAILABLE
        assert v.features_schema_fingerprint() == v.UNAVAILABLE
    finally:
        monkeypatch.undo()
        v.ruleset_fingerprint.cache_clear()
        v.features_schema_fingerprint.cache_clear()


# ── the evaluation records them ─────────────────────────────────────────────



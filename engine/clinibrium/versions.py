"""Clinical version identifiers recorded with every evaluation (plan J).

Two kinds of identifier per artefact:
- a SEMANTIC version declared by hand (bumped with every clinical change that
  is signed off), and
- a FINGERPRINT computed from what actually runs (rule tables, criteria,
  thresholds and the engines' source; the CaseFeatures schema and its
  validators).

tests/test_versions.py checks the (version, fingerprint) pair against the
approved manifest `versions_manifest.json`: changing a rule without a NEW
version fails the gate, and a version can never be reused for different
content. Pure: no I/O beyond reading imported modules' source.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from functools import lru_cache
from types import ModuleType

RULESET_VERSION = "0.2.0-S1-P"
FEATURES_SCHEMA_VERSION = "2"
# Plan T1 (AD-28): the evaluation path always uses the inline corpus; this
# names it. Bump it (and append to the manifest) when the corpus or its
# selection logic changes.
GROUNDING_VERSION = "1"
UNAVAILABLE = "unavailable"


def _ruleset_modules() -> list[ModuleType]:
    from clinibrium.differential_engine import criteria as dx_criteria
    from clinibrium.differential_engine import engine as dx_engine
    from clinibrium.rails import engine as rails_engine
    from clinibrium.rails import ordering as rails_ordering
    from clinibrium.rails import thresholds as rails_thresholds
    from clinibrium.redflag_engine import engine as rf_engine
    from clinibrium.redflag_engine import rules as rf_rules

    return [rf_rules, rf_engine, dx_criteria, dx_engine, rails_engine, rails_ordering,
            rails_thresholds]


def _features_modules() -> list[ModuleType]:
    from clinibrium.contracts import enums, features

    return [features, enums]


def _digest(parts: list[str]) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.replace("\r\n", "\n").encode("utf-8") + b"\0")
    return h.hexdigest()[:12]


def _sources(modules: list[ModuleType]) -> list[str]:
    # Fixed order; module NAME is part of the hash so moving code between
    # modules is also a visible change.
    return [f"{m.__name__}\n{inspect.getsource(m)}" for m in modules]


@lru_cache(maxsize=1)
def ruleset_fingerprint() -> str:
    try:
        return _digest(_sources(_ruleset_modules()))
    except (OSError, TypeError):  # no source available (e.g. bytecode-only install)
        return UNAVAILABLE


@lru_cache(maxsize=1)
def grounding_fingerprint() -> str:
    """Corpus text + selection logic of the inline grounding (plan T1)."""
    from clinibrium.grounding import inline

    try:
        return _digest(_sources([inline]))
    except (OSError, TypeError):
        return UNAVAILABLE


@lru_cache(maxsize=1)
def features_schema_fingerprint() -> str:
    from clinibrium.contracts.features import CaseFeatures

    schema = json.dumps(CaseFeatures.model_json_schema(), sort_keys=True, separators=(",", ":"))
    try:
        return _digest([schema, *_sources(_features_modules())])
    except (OSError, TypeError):
        return UNAVAILABLE

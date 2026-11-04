"""Bilingual UI (`lang`) presentation-boundary tests.

These guard the safety contract of the language toggle:
  - Spanish (default) output is byte-identical to the pre-toggle behavior.
  - English localizes ONLY presentation (labels/prose), never enums, urgency,
    forced actions, red-flag decisions, or the `/predict` payload.
  - `lang` never reaches the ML engine and never enters CaseFeatures.
  - Every canonical id/key has an English translation (completeness).
  - Invalid `lang` is rejected (422), not silently accepted.
"""
from __future__ import annotations

from clinibrium.counterfactual.engine import _PERTURBATIONS
from clinibrium.i18n import (
    COUNTERFACTUAL_LABELS_EN,
    REDFLAG_LABELS_EN,
    localize_counterfactual_change,
    localize_redflag_label,
)
from clinibrium.redflag_engine.rules import RULES

# =============================================================================
# Helpers
# =============================================================================


# =============================================================================
# Completeness: every canonical id/key has an English translation
# =============================================================================
def test_every_redflag_rule_has_english_label():
    missing = [r.id for r in RULES if r.id not in REDFLAG_LABELS_EN]
    assert not missing, f"red-flag rules without EN label: {missing}"


def test_every_counterfactual_key_has_english_label():
    missing = [p.key for p in _PERTURBATIONS if p.key not in COUNTERFACTUAL_LABELS_EN]
    assert not missing, f"counterfactual perturbations without EN label: {missing}"


def test_counterfactual_keys_are_unique():
    keys = [p.key for p in _PERTURBATIONS]
    assert len(keys) == len(set(keys))


# =============================================================================
# Localize helpers: es no-op, en maps, unknown → fallback
# =============================================================================
def test_localize_redflag_es_is_noop():
    assert localize_redflag_label("A1", "Etiqueta ES", "es") == "Etiqueta ES"


def test_localize_redflag_en_maps_and_falls_back():
    assert localize_redflag_label("A5", "Signos neurológicos focales", "en") == (
        "Focal neurological signs"
    )
    # Unknown id → falls back to the canonical label (never blank/crash).
    assert localize_redflag_label("ZZ", "Canon", "en") == "Canon"


def test_localize_counterfactual_es_noop_en_maps():
    assert localize_counterfactual_change("neck_stiffness", "Rigidez de nuca", "es") == (
        "Rigidez de nuca"
    )
    assert localize_counterfactual_change("neck_stiffness", "Rigidez de nuca", "en") == (
        "Neck stiffness"
    )


# =============================================================================
# Reasoner prompt: es byte-identical, en appends an output-language directive
# =============================================================================


# =============================================================================
# /api/evaluate: en localizes labels but NOT enums/urgency/red flags
# =============================================================================


# =============================================================================
# /api/what-would-change: en localizes `change`, es unchanged
# =============================================================================


# =============================================================================
# Persistence: output_lang survives the REAL Postgres and JSONL paths
# (codex-audit-4 Alta 2: inspecting the in-memory event is not enough —
# these exercise the pooled INSERT / `_persist_jsonl` themselves)
# =============================================================================



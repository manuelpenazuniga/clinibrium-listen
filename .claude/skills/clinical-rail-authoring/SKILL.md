---
name: clinical-rail-authoring
description: Turns a safety rule SIGNED by the clinical specialist into a verifiable change to the Clinibrium RedFlagEngine/rails (engine/clinibrium), with mandatory adversarial tests and invariant runs. Claude NEVER decides clinical content nor claims validation; it stops on ambiguity. Use it only when the specialist signs a new red flag / rail / threshold AND the repo owner explicitly unfreezes engine/.
---

# Clinical Rail Authoring — Safety Harness

(Ported from Clinibrium. In Clinibrium Listen the engine is **frozen**: SPECS §0.1
says `engine/` is ported pre-existing work and its thresholds, rules, weights
and rails are never edited. This skill applies only after the repo owner
explicitly unfreezes `engine/` for a specialist-signed change.)

Guide for turning a **safety rule signed by the specialist** into verifiable
code, without the model deciding anything clinical. *Claude turns human
expertise into verifiable artefacts; the deterministic runtime makes them
trustworthy.*

## Preconditions — if ANY is missing, STOP and hand the question back to the human
- The rule is **signed by the specialist**, not inferred by the model.
- The repo owner has **explicitly unfrozen** `engine/` for this change.
- It is expressed as **conditions → forced action**, using ONLY:
  - fields of the `CaseFeatures` allowlist (`engine/clinibrium/contracts/features.py`);
  - existing enums (`engine/clinibrium/contracts/enums.py`);
  - one or more `ForcedAction`s (`DERIVAR_URGENTE`, `NO_BENIGNO`, `BLOQUEAR_EPLEY`,
    `PRECAUCION_EXAMEN`, `RED_SEGURIDAD`, `ESCALAR`).
- It does NOT introduce a new diagnosis or a numeric threshold the specialist did not set.

## Procedure (in order)
1. **Map** the rule onto the existing deterministic tables:
   - Red flag → a `RedFlagRule(id, label, severity, forced_actions, predicate)` in
     `engine/clinibrium/redflag_engine/rules.py` (`predicate` is a pure function of `CaseFeatures`).
   - Contraindication / Epley block / escalation → `engine/clinibrium/rails/engine.py`.
   - Reuse existing helpers (`_avs`, …); do not duplicate logic.
   - Add the English label to `engine/clinibrium/i18n/labels.py`.
2. **Version it.** Any rule change moves the ruleset fingerprint: bump
   `RULESET_VERSION` in `engine/clinibrium/versions.py` and APPEND the new
   (version, fingerprint) pair to `versions_manifest.json` (never edit an existing pair).
3. **Write MANDATORY adversarial tests** (before or with the code):
   - **positive** (fires), **negative** (does not fire) and **edge**;
   - a **monotonicity (INV-7)** test: the rule never LOWERS urgency;
   - if it is a central red flag, that it **forces `inmediata` (INV-1)**;
   - update the S0 regression matrix snapshot only if the specialist signed the change.
4. **Run the invariants.** The hook `.claude/hooks/verify-clinical-invariants.sh`
   runs them automatically on save. Manually:
   `uv run pytest -q engine/tests api/tests/test_invariants_*.py`.
   Listen-side guarantees that must still hold: adapter parity
   (`engine/tests/test_adapter_parity.py`) and L1–L11 (`api/tests/test_invariants_*.py`).
   If the rule adds a field, regenerate `config/field_catalog.json`
   (`scripts/gen_catalog.py`) and `web/lib/contracts.ts` (`scripts/gen_contracts.sh`).
5. **Change report** (short): which rule, which `RedFlagRule`/rail, new tests,
   invariants run and their result, and the diff.
6. **Stop on clinical ambiguity**: if the rule is not univocal (threshold without
   a number, "per clinical judgment", unspecified combination) do NOT guess —
   mark `# TODO(clinical)` and return the question to the specialist.
7. **NEVER** claim clinical validation, sign for the specialist, or assert
   regulatory compliance. Provisional content is labelled `# TODO(clinical)`.

## Invariants no change may break (the hook checks them)
- **INV-1** — `red_flag_activa ⇒ urgency == inmediata` (always wins).
- **INV-5** — `RedFlagEngine ⟂ DifferentialEngine` (no coupling through imports).
- **INV-7** — rails only RAISE urgency (monotonicity), idempotence, totality.
- **L1** — unconfirmed values can raise urgency/blocks, never lower them.
- **L3** — models never set urgency or actions.
- **L11** — urgency ordering always uses `clinibrium.rails.ordering.urgency_max` /
  the rank table, never Python's `max()` on `Urgency` (a str enum: it sorts alphabetically).

## Safety bias (non-negotiable)
Provisional values are calibrated toward **over-triage**: a false positive
(over-referral) is tolerable; a false negative (a missed emergency) is not. The
specialist may *lower* thresholds; the system never *raises* the risk of a miss
by default. **The physician always decides.**

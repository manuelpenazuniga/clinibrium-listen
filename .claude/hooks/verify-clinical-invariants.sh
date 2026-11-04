#!/usr/bin/env bash
# Safety Harness — PostToolUse hook (ported from Clinibrium, adapted to Listen).
#
# When Claude Code edits a SAFETY-CRITICAL file (frozen engine, adapter, the
# Listen policy/evidence/planner/session, model contracts or the field
# catalog), this runs the relevant INVARIANT tests. On failure it exits 2, so
# Claude sees stderr and does not carry on as if nothing happened.
#
# Fails soft: if the file is not safety-critical, there is no venv, or the
# input cannot be parsed, it does NOT block (exit 0). It never blocks an edit
# that does not touch safety.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

INPUT="$(cat 2>/dev/null || true)"
FILE="$(printf '%s' "$INPUT" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null || true)"

ENGINE_TESTS="engine/tests/test_redflag_engine.py engine/tests/test_rails.py \
engine/tests/test_differential_engine.py engine/tests/test_s0_properties.py \
engine/tests/test_s0_regression_matrix.py engine/tests/test_s1_action_conservation.py \
engine/tests/test_p_not_assessed.py engine/tests/test_counterfactual.py \
engine/tests/test_counterfactual_severity.py engine/tests/test_versions.py \
engine/tests/test_adapter_parity.py"
LISTEN_TESTS="$(cd "$ROOT" && ls api/tests/test_invariants_*.py 2>/dev/null | tr '\n' ' ')"

case "$FILE" in
  *engine/clinibrium/redflag_engine/*|*engine/clinibrium/rails/*|*engine/clinibrium/differential_engine/*|*engine/clinibrium/contracts/*|*engine/clinibrium/counterfactual/*|*engine/clinibrium/grounding/*|*engine/clinibrium/versions*|*engine/adapter.py)
    TESTS="$ENGINE_TESTS $LISTEN_TESTS"
    INV="INV-1 (red flag ⇒ inmediata) · INV-5 (separation) · INV-7 (rail monotonicity) · ruleset fingerprint · adapter parity · L1–L11"
    ;;
  *api/listen/*|*api/muse/*|*config/field_catalog.json|*config/protocol.json|*config/referral_labels.json|*scripts/gen_catalog.py)
    TESTS="engine/tests/test_adapter_parity.py api/tests/test_contracts_schema.py api/tests/test_catalog.py $LISTEN_TESTS"
    INV="L1–L11 (conservative policy, evidence, kill switch, planner, letter, receipt, egress, epochs, urgency ordering) · contracts · catalog"
    ;;
  *)
    exit 0  # not safety-critical → silent no-op
    ;;
esac

PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || exit 0            # no venv → do not block
cd "$ROOT" 2>/dev/null || exit 0

# shellcheck disable=SC2086
if OUT="$("$PY" -m pytest -q -p no:cacheprovider $TESTS 2>&1)"; then
  echo "✓ Safety Harness — clinical invariants OK after editing $(basename "$FILE"): $INV" >&2
  exit 0
else
  {
    echo "🚨 Safety Harness — CLINICAL INVARIANTS FAILED after editing $(basename "$FILE")."
    echo "   Checked: $INV"
    echo "   The change may have broken a safety guarantee. Do NOT continue until it is fixed."
    echo "   ---- pytest (tail) ----"
    printf '%s\n' "$OUT" | tail -20
  } >&2
  exit 2
fi

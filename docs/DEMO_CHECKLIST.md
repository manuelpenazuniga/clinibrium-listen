# Demo checklist — SPECS §8 in replay mode (Phase 2a)

Run: 2026-11-04. The **real API** ran with `MUSE_MODE=replay` (offline; replays
from `fixtures/replays/{A,B,phrasing}`, `MODEL_API_KEY` unset, `MUSE_RECORD=0`),
against the **production web build** (`pnpm build && pnpm start`, not the web
mock). The test drives Chromium through every clinician action with Playwright.
A second WebSocket to the same session reads every `SessionState` snapshot, so
each item is checked on the server's state as well as on the screen.

Reproduce from the repo root:

```bash
web/e2e/run-replay.sh
```

It writes `web/e2e/out/results.json` and screenshots, which are not committed.
The **live** run of the same script is Phase 2b.

**Result: 26/26 checks pass. One informational item, explained below.**

## Case A — right posterior BPPV

| # | Step | Result | Observed |
|---|---|---|---|
| 1 | "Play demo case" picker offers only A and B (the API serves 12 bench cases) | ✅ | `Abrir caso A`, `Abrir caso B` |
| 2 | The session runs on the real API, not the mock | ✅ | API session id, not `mock-…` |
| 3 | Planner asks for Dix-Hallpike | ✅ | "¿Cuál fue el resultado del Dix-Hallpike: positivo derecho, izquierdo, bilateral o negativo?" Reason: "si dix_hallpike=right_positive, torsion…=sí, nystagmus_fatigable=sí → Ambulatoria desbloquea Epley…" |
| 4 | "Positivo derecho, torsional, se agota" is extracted as an answer | ✅ | `dix_hallpike=right_positive` (source `answered`), plus torsion and fatigability |
| 5 | Before confirmation: **Prioritaria**, Epley blocked (L1) | ✅ | urgency `prioritaria`, blocked `EPLEY` |
| 6 | **Visible clinician-confirm step**; the player confirms nothing by itself | ✅ | "Paso del clínico" card listing 11 proposals; 0 confirmed after waiting 3 s |
| 7 | Clinician taps confirm → **Ambulatoria**, Epley not blocked | ✅ | top-1 `bppv_posterior`, "Manejo ambulatorio / control en APS" |
| 8 | Decision card shows Ambulatoria | ✅ | |
| 9 | Finalize → letter + receipt | ✅ | 6 letter sections, receipt SHA-256 |
| 10 | Reasoner explanation (replay) | ✅ | `muse-spark-1.3`, `citations_verified=true` |
| 11 | **Verify** turns green | ✅ | "Verificado: SHA-256 coincide" (WebCrypto over `canonical_json`) |
| 12 | No browser console errors, no `state.errors` | ✅ | |

## Case B — acute vestibular syndrome with buried diplopia

| # | Step | Result | Observed |
|---|---|---|---|
| 1 | "…ayer vio doble un rato…" → diplopia proposed as a **sticky alert** | ✅ | `focal_signs.diplopia=true`, quote "vio doble un rato" |
| 2 | Diplopia **conflict** | ℹ️ | No conflict opens: see the note below |
| 3 | **Inmediata**, Epley blocked | ✅ | red flags A5\*, A7\* (provisional) |
| 4 | **Stroke time window** | ✅ | Last known well 12 h ago; early stroke window (4 h 30 min) closed, extended stroke window (24 h) open; defaults to set per local protocol |
| 5 | **Advocate** raises a confirmation request | ✅ | `focal_signs.diplopia=true`, quote "Ayer vio doble un rato"; the advocate floor is active |
| 6 | **Medication photo** → proposes *anticoagulado* | ✅ | `context.anticoagulated=true` (source `document`), quote "Acenocumarol según control de TACO" |
| 7 | Clinician confirms the advocate request | ✅ | diplopia confirmed; floor off |
| 8 | Clinician resolves everything (clinician-confirm step) | ✅ | finalize unblocked, urgency `inmediata`, `source_eval=confirmed` |
| 9 | **Kill switch** with B's red flag confirmed | ✅ | urgency stays **Inmediata**. Blocked (`EPLEY`), forced actions (`BLOQUEAR_EPLEY, DERIVAR_URGENTE, ESCALAR, NO_BENIGNO`) and the clock are identical before and after (L4) |
| 10 | Kill switch off → Finalize → letter + receipt | ✅ | |
| 11 | Reasoner explanation (replay) | ✅ | `muse-wonder-1.0` (red flag shown), `citations_verified=true` |
| 12 | **Verify** turns green | ✅ | "Verificado: SHA-256 coincide" |
| 13 | No browser console errors, no `state.errors` | ✅ | |

### Note on the case-B conflict (ℹ️)

SPECS §8 does not ask for a conflict in case B. That item came from the
hand-written 1C web mock, which invents a `diplopia=false` proposal from
"ahora no".

The real extractor recording does **not** propose `false` for "ayer vio doble un
rato, ahora no". It records `true`, which is correct: extractor prompt rule 4
says a transient symptom counts as present. With no contradicting proposal,
`policy.merge` has nothing to put in conflict. The clinician clears the sticky
alert through the advocate request instead (steps 5 and 7).

The conflict UI and the policy are still covered:
- the 1A policy tests (`test_listen_units.py`, `test_invariants_listen.py` L5);
- the 1C mock, which still shows a conflict for case B.

Faking a conflict in replay would mean a fabricated recording, so it was not done.

## Bench

`uv run python bench/run.py --mode replay` gives the same accuracy numbers as
the live run, offline. It now also reports the planner's questions: baseline 19,
Muse 21 across 12 cases. See `bench/results/table.md`.

The latencies in replay mode are local lookups, not Meta latencies. The live
latencies are in `bench/results/live.json`.

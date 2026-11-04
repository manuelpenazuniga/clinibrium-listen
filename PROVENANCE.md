# Provenance

- **Pre-existing, ported:** `engine/clinibrium/*` (deterministic red-flag engine,
  ICVD differential, rails, counterfactual engine, inline grounding) and the
  `.claude/` harness, from Clinibrium (Apache-2.0, built July–October 2026).
- **Built during the hackathon (Oct 27 – Nov 4, 2026):** everything else,
  including the voice workflow, the Meta Model API integration (Voice Transcribe
  relay, extractor, phrasing, advocate, vision, reasoner, replay), evidence
  validation, the conservative policy and L1–L11, the question planner, window
  clock, deterministic letter, receipt, web app and bench.
- The demo video shows only the new work.

## Port details (Phase 0)

- `engine/clinibrium/` is byte-identical to the source `backend/clinibrium/`
  for every ported module **except** `grounding/factory.py`, which now always
  returns the inline grounding (the pgvector backend and its `asyncpg`/`pgvector`
  dependencies were not ported). The source evaluation path already used the
  inline corpus only. `engine/tests/test_versions.py` proves the rules are
  unchanged: the ruleset, features-schema and grounding fingerprints match the
  approved `versions_manifest.json` pairs.
- Ported tests live in `engine/tests/`. Tests that exercised modules that were
  not ported (API, orchestrator, audit emission, FHIR, storage, ML client,
  reasoner, bench) were removed function by function; see the Phase 0 report
  in the PR/commit history.
- `engine/tests/fixtures/bench_dev/` vendors the 20 source bench dev cases
  (de-identified `CaseFeatures` only) and `demo_presets.json` the 3 tutorial
  presets, used by the counterfactual snapshot and adapter parity tests.
- `web/components/ui/orb.tsx` and `waveform.tsx` are adapted from MIT-licensed
  visual components (see `web/THIRD_PARTY_NOTICES.md`).

# Bench — Muse extractor vs keyword baseline

> Research prototype · Not for clinical use · The physician decides.

## What it measures

The bench asks one question: **when a physician dictates a vertigo case, does the
structured form that comes out lead the deterministic engine to the same decision
as the gold form?** It compares two extractors on the same scripted dictations:

- **Keyword baseline** (`baseline.py`): catalog lexicon + regex, sentence-level
  negation (`sin`, `no`, `niega`, … within 4 tokens), no model.
- **Muse extractor**: whatever `api/muse` serves for `MUSE_MODE` (`mock` =
  deterministic lexicon fake, `replay` = recorded Meta responses, `live` = Meta
  Model API).

Each system reads the dictation **turn by turn** (with the prior turns and the
current values as context), then each scripted answer with its question pending.
Short answers (`sí`, `no`, `no lo evalué`) go through the same deterministic
classifier as the product (SPECS §6.1) before any extractor. Muse deltas must pass
the E-quote check (quote is a substring of the turn) and the catalog type check;
failing deltas are dropped and counted. Extracted atomic fields are projected to
`CaseFeatures` (SPECS §5.1) and evaluated with the frozen engine (`engine/adapter.py`).

## Cases (`cases/*.json`)

12 scripted Chilean-Spanish dictations, same shape as `api/demo_cases.py`
(`GET /api/demo-cases` serves them):

| Id | Category | Gold urgency |
|---|---|---|
| A | BPPV — demo case A | ambulatoria |
| B | Buried central red flag (diplopia) — demo case B | inmediata |
| C | BPPV, left, older patient | ambulatoria |
| D | Ménière-like | ambulatoria |
| E | Vestibular migraine | ambulatoria |
| F | Buried central red flag (dysarthria told by family, paraphrased) | inmediata |
| G | Negation-heavy (vestibular neuritis) | ambulatoria |
| H | Corrections inside a sentence | ambulatoria |
| I | Buried red flag (sudden neck pain) | inmediata |
| J | Presyncope presenting as "mareo" | prioritaria |
| K | Ambiguous / non-specific | prioritaria |
| L | Short answers, incl. "no lo evalué" | ambulatoria |

Gold labels:
- `gold.fields` — the atomic keys (from `config/field_catalog.json`) that the
  dictation actually states. Unstated = absent = *not assessed*.
- `gold.urgency` — **computed, never hand-labelled**: the engine on the gold
  projection (`uv run python bench/gold.py --write`; the tests fail when stale).
- `gold.top1_dx` — hand label for benign cases (checked against the engine's
  top-1 on the gold fields); `null` when a central red flag makes the differential moot.
- `gold.first_question_key` — optional expected first question.

## Metrics

| Metric | Definition |
|---|---|
| Per-key accuracy | gold keys extracted with exactly the gold value / all gold keys |
| Key precision | correct keys / all keys the system produced |
| Red-flag recall | engine red flags on extracted fields ∩ on gold fields / on gold fields |
| Negation accuracy | gold "assessed, absent" keys (`false`, `none`, `negative`) extracted correctly |
| Negation flips | gold `false` extracted as `true` (the dangerous direction for L2) |
| Urgency agreement | engine urgency on extracted fields == gold urgency |
| Under-triaged cases | extracted urgency strictly lower than gold (rank table, never `max()`) |
| Top-1 dx agreement | engine top-1 on extracted fields == `gold.top1_dx` (when set) |
| Questions asked | from `api/listen/planner` when wired; `n/a` otherwise |
| Latency | wall time per extractor call |
| Cost estimate | ≈ chars/4 tokens × `BENCH_PRICE_IN_PER_MTOK` / `BENCH_PRICE_OUT_PER_MTOK` (USD per 1M tokens); `n/a` if unset; 0 for mock |

## Running

```bash
uv run python bench/run.py --mode mock
```

```bash
uv run python bench/run.py --mode replay
```

```bash
MUSE_MAX_LIVE_CALLS=40 uv run python bench/run.py --mode live
```

- `mock` and `replay` run with outbound sockets disabled: any connection attempt raises.
- `live` prints the planned number of extractor calls and refuses to run unless
  `MUSE_MAX_LIVE_CALLS` is set and the plan fits; the runner also stops at the cap.
  `--cases A,B` limits the run.
- Outputs: `results/<mode>.json` (full detail, per case and per key),
  `results/table.md` and `results/table.json` (for the README and the web `/bench` page).

## Limits — read before quoting a number

- **Synthetic and scripted.** Twelve dictations written by the team to cover
  specific failure modes; not a sample of real practice, no real patients, no
  clinician-adjudicated gold. Numbers describe these scripts, nothing more.
- **Text, not audio.** The turns are clean text; ASR errors are not measured.
- **Gold urgency comes from the same engine** the systems feed, so the bench
  measures extraction fidelity as seen through the engine, not the engine's
  clinical validity.
- **In `mock` mode the "Muse" column is a lexicon fake**, close to the baseline
  by construction. It exercises the pipeline; it says nothing about Meta's models.
  Only `replay`/`live` results compare a model with the baseline.
- Some cases are deliberately outside the lexicon (paraphrased dysarthria in F,
  "se va a desmayar" in J, "niega hipoacusia" in C, "oído derecho tapado" in D),
  so the baseline is expected to miss them.
- The bench does not run the full session policy (sticky alerts, conflicts,
  conservative C/C∪P evaluation, advocate floor): extracted values are taken as
  given and the last value per key wins. Documents (photos) are not evaluated.
- Latency in `mock` is local CPU time; the cost column is a character-count estimate.

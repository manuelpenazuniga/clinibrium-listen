# Bench results — mode `mock`

12 scripted cases · generated 2026-11-04T05:46:23Z · Muse extractor: `mock-extractor`

Synthetic, scripted dictations; not a clinical validation. See bench/README.md.

| Metric | Keyword baseline | Muse |
|---|---|---|
| Per-key accuracy | 0.938 | 0.956 |
| Key precision | 0.955 | 0.973 |
| Red-flag recall | 0.800 | 0.800 |
| Negation accuracy | 0.972 | 0.972 |
| Negation flips (absent → present) | 0 | 0 |
| Urgency agreement vs gold | 0.917 | 0.917 |
| Under-triaged cases | 1 | 1 |
| Top-1 dx agreement | 1.000 | 1.000 |
| Questions asked | n/a | n/a |
| Latency per call, mean (ms) | 3.9 | 6.0 |
| Latency per call, p95 (ms) | 5.5 | 8.6 |
| Cost estimate (USD) | 0.000 | 0.000 |

| Case | Gold urgency | Baseline | Muse | Keys ✓ baseline | Keys ✓ Muse |
|---|---|---|---|---|---|
| Case A — right posterior BPPV | ambulatoria | ambulatoria | ambulatoria | 11/11 | 11/11 |
| Case B — acute vestibular syndrome with buried diplopia | inmediata | inmediata | inmediata | 10/10 | 10/10 |
| Case C — left posterior BPPV, older woman | ambulatoria | ambulatoria | ambulatoria | 11/12 | 11/12 |
| Case D — Ménière-like attacks | ambulatoria | ambulatoria | ambulatoria | 8/9 | 8/9 |
| Case E — vestibular migraine | ambulatoria | ambulatoria | ambulatoria | 8/8 | 8/8 |
| Case F — AVS with transient dysarthria reported by family | inmediata | **ambulatoria** ✗ | **ambulatoria** ✗ | 6/7 | 6/7 |
| Case G — vestibular neuritis, negation-heavy | ambulatoria | ambulatoria | ambulatoria | 18/19 | 18/19 |
| Case H — BPPV with dictation corrections | ambulatoria | ambulatoria | ambulatoria | 8/10 | 10/10 |
| Case I — AVS with buried sudden neck pain | inmediata | inmediata | inmediata | 9/9 | 9/9 |
| Case J — presyncope presenting as “dizziness” | prioritaria | prioritaria | prioritaria | 6/7 | 6/7 |
| Case K — nonspecific dizziness, ambiguous dictation | prioritaria | prioritaria | prioritaria | 2/2 | 2/2 |
| Case L — vestibular neuritis with short answers | ambulatoria | ambulatoria | ambulatoria | 9/9 | 9/9 |

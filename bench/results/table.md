# Bench results — mode `live`

12 scripted cases · generated 2026-11-04T11:36:16Z · Muse extractor: `muse-spark-1.3`

Synthetic, scripted dictations; not a clinical validation. See bench/README.md.

| Metric | Keyword baseline | Muse |
|---|---|---|
| Per-key accuracy | 0.938 | 0.973 |
| Key precision | 0.955 | 0.902 |
| Red-flag recall | 0.800 | 1.000 |
| Negation accuracy | 0.972 | 1.000 |
| Negation flips (absent → present) | 0 | 0 |
| Urgency agreement vs gold | 0.917 | 1.000 |
| Under-triaged cases | 1 | 0 |
| Top-1 dx agreement | 1.000 | 1.000 |
| Questions asked | n/a | n/a |
| Latency per call, mean (ms) | 4.0 | 3872.8 |
| Latency per call, p95 (ms) | 6.8 | 5752.4 |
| Cost estimate (USD) | 0.000 | n/a |

| Case | Gold urgency | Baseline | Muse | Keys ✓ baseline | Keys ✓ Muse |
|---|---|---|---|---|---|
| Case A — right posterior BPPV | ambulatoria | ambulatoria | ambulatoria | 11/11 | 11/11 |
| Case B — acute vestibular syndrome with buried diplopia | inmediata | inmediata | inmediata | 10/10 | 10/10 |
| Case C — left posterior BPPV, older woman | ambulatoria | ambulatoria | ambulatoria | 11/12 | 10/12 |
| Case D — Ménière-like attacks | ambulatoria | ambulatoria | ambulatoria | 8/9 | 9/9 |
| Case E — vestibular migraine | ambulatoria | ambulatoria | ambulatoria | 8/8 | 8/8 |
| Case F — AVS with transient dysarthria reported by family | inmediata | **ambulatoria** ✗ | inmediata | 6/7 | 7/7 |
| Case G — vestibular neuritis, negation-heavy | ambulatoria | ambulatoria | ambulatoria | 18/19 | 19/19 |
| Case H — BPPV with dictation corrections | ambulatoria | ambulatoria | ambulatoria | 8/10 | 10/10 |
| Case I — AVS with buried sudden neck pain | inmediata | inmediata | inmediata | 9/9 | 9/9 |
| Case J — presyncope presenting as “dizziness” | prioritaria | prioritaria | prioritaria | 6/7 | 7/7 |
| Case K — nonspecific dizziness, ambiguous dictation | prioritaria | prioritaria | prioritaria | 2/2 | 1/2 |
| Case L — vestibular neuritis with short answers | ambulatoria | ambulatoria | ambulatoria | 9/9 | 9/9 |

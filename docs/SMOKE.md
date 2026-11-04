# Meta Model API smoke test (Phase 0)

Run: 2026-11-04T05:21:41+00:00 · base URL `https://api.meta.ai/v1` · script `scripts/smoke_meta.py`.
Key read from `MODEL_API_KEY` (never logged).

| Check | Result |
|---|---|
| (a) `GET /v1/models` lists the 3 models | ✅ PASS |
| (b) strict `json_schema` → `{"deltas":[...]}` from muse-spark-1.3 | ✅ PASS |
| (c) `POST /v1/asr/transcribe` returns Spanish text | ✅ PASS |

## (a) Models
```json
{
  "status": 200,
  "latency_ms": 845,
  "models": [
    "muse-image-1.0",
    "muse-spark-1.1",
    "muse-spark-1.2",
    "muse-spark-1.2-contributor",
    "muse-spark-1.3",
    "muse-spark-1.3-contributor",
    "muse-voice-transcribe-1.0",
    "muse-wonder-1.0",
    "sam-3.1"
  ],
  "missing": [],
  "ok": true
}
```

## (b) Strict structured output
Input: `Paciente de 68 años, vértigo continuo hace 12 horas, sin diplopía.`
```json
{
  "attempts": [
    {
      "reasoning_effort": "minimal",
      "status": 200,
      "latency_ms": 5968,
      "usage": {
        "completion_tokens": 736,
        "prompt_tokens": 388,
        "total_tokens": 1124,
        "completion_tokens_details": {
          "reasoning_tokens": 423
        },
        "prompt_tokens_details": {
          "cached_tokens": 369
        }
      }
    }
  ],
  "raw_content": "{\"deltas\": [{\"answers_question_id\": null, \"confidence_pct\": 100, \"key\": \"age_years\", \"quote\": \"68 a\\u00f1os\", \"value_bool\": null, \"value_enum\": null, \"value_int\": 68, \"value_text\": null}, {\"answers_question_id\": null, \"confidence_pct\": 95, \"key\": \"duration\", \"quote\": \"hace 12 horas\", \"value_bool\": null, \"value_enum\": \"hours\", \"value_int\": null, \"value_text\": null}, {\"answers_question_id\": null, \"confidence_pct\": 90, \"key\": \"timing_pattern\", \"quote\": \"v\\u00e9rtigo continuo\", \"value_bool\": null, \"value_enum\": \"acute_continuous\", \"value_int\": null, \"value_text\": null}, {\"answers_question_id\": null, \"confidence_pct\": 100, \"key\": \"focal_signs.diplopia\", \"quote\": \"sin diplop\\u00eda\", \"value_bool\": false, \"value_enum\": null, \"value_int\": null, \"value_text\": null}, {\"answers_question_id\": null, \"confidence_pct\": 95, \"key\": \"context.last_known_well_minutes_ago\", \"quote\": \"hace 12 horas\", \"value_bool\": null, \"value_enum\": null, \"value_int\": 720, \"value_text\": null}]}",
  "ok": true,
  "deltas": [
    {
      "key": "age_years",
      "value_bool": null,
      "value_int": 68,
      "value_enum": null,
      "value_text": null,
      "quote": "68 años",
      "confidence_pct": 100,
      "answers_question_id": null
    },
    {
      "key": "duration",
      "value_bool": null,
      "value_int": null,
      "value_enum": "hours",
      "value_text": null,
      "quote": "hace 12 horas",
      "confidence_pct": 95,
      "answers_question_id": null
    },
    {
      "key": "timing_pattern",
      "value_bool": null,
      "value_int": null,
      "value_enum": "acute_continuous",
      "value_text": null,
      "quote": "vértigo continuo",
      "confidence_pct": 90,
      "answers_question_id": null
    },
    {
      "key": "focal_signs.diplopia",
      "value_bool": false,
      "value_int": null,
      "value_enum": null,
      "value_text": null,
      "quote": "sin diplopía",
      "confidence_pct": 100,
      "answers_question_id": null
    },
    {
      "key": "context.last_known_well_minutes_ago",
      "value_bool": null,
      "value_int": 720,
      "value_enum": null,
      "value_text": null,
      "quote": "hace 12 horas",
      "confidence_pct": 95,
      "answers_question_id": null
    }
  ],
  "unknown_keys": [],
  "non_verbatim_quotes": [],
  "diplopia_false": true,
  "model": "muse-spark-1.3"
}
```

## (c) File ASR
```json
{
  "wav": {
    "channels": 1,
    "sample_width": 2,
    "rate": 16000,
    "seconds": 6.3
  },
  "request": {
    "model": "muse-voice-transcribe-1.0",
    "languageBias": [
      "Spanish"
    ],
    "audioEncoding": "WAV"
  },
  "status": 200,
  "latency_ms": 2295,
  "response_keys": [
    "audioDurationMs",
    "sessionId",
    "transcript",
    "turns"
  ],
  "turns": [],
  "audio_duration_ms": 6320,
  "ok": true,
  "transcript": "paciente de sesenta y ocho años, vértigo continuo hace doce horas, sin diplopía.",
  "spanish_hits": [
    "paciente",
    "vertigo",
    "horas",
    "diplopia"
  ]
}
```

## Corrections to SPECS §3.1
- `/v1/asr/transcribe`: the `request` JSON REQUIRES `audioEncoding` (HTTP 400 "You must specify the 'audioEncoding' field" without it); `"WAV"` is accepted.
- ASR response keys are ['audioDurationMs', 'sessionId', 'transcript', 'turns']: full text at top-level `transcript`; `turns` had 0 item(s) for a 6.3 s clip, so consumers must fall back to `transcript` when `turns` is empty.
- Strict `json_schema` works as specified; `reasoning_effort=minimal` accepted on muse-spark-1.3. The schema from `api.listen.contracts.strict_json_schema(ExtractorOut)` (refs inlined, all properties required, nullable optionals) was accepted unchanged.

## Phase 2b — live end to end and deploy (2026-11-04, local)

### Live end to end (MUSE_MODE=live, local API, access code, caps on)
- **Case A, typed (real session over WS):**
  - Live phrasing asks Dix-Hallpike, and the answer is extracted as `right_positive`, torsional, fatigable.
  - Before confirmation it is Prioritaria with Epley blocked (L1). After `confirm_all` it is Ambulatoria with Epley not blocked; top-1 is `bppv_posterior`.
  - Finalize produces the letter and the receipt. The Spark reasoner runs with verified citations.
- **Case B, typed, plus the medication photo:**
  - Inmediata, with the window clock; live vision proposes `anticoagulated`; the advocate request is raised.
  - The kill switch leaves urgency, blocks and forced actions unchanged (L4).
  - Finalize works, and the Wonder reasoner runs with verified citations.
  - On one live pass the extractor missed the buried "vio doble". The advocate caught it, and the case ended Inmediata. This is the safety net working as designed.
- **Audio:** the scripted WAV was streamed over the WS as 100 ms frames.
  - Live partials reach the UI, and the final transcript becomes a turn.
  - "sesenta y ocho años" is extracted as `age_years=68` (spoken numbers handled in code).
- **Bugs found and fixed** (PR `phase2b/live-fixes`):
  - The final pass used the 12 s turn timeout, but the live reasoner takes 15–20 s, so every live explanation came back "unavailable". The final pass now has `FINAL_PASS_TIMEOUT_S = 45`.
  - A request cancelled by a timeout left no ledger row, so the caps could undercount. It is now recorded as `cancelled`.
- The fail-closed guard also tripped as designed when the Wonder cap (10) was reached (`advocate_unavailable: BudgetExceeded`).
- One transient Meta HTTP 503 on a reasoner call.

### Deployed (public, replay only — zero Meta calls)
- **Web:** https://clinibrium-listen.vercel.app (Vercel, root `web/`).
- **API:** https://api-production-201e.up.railway.app (Railway, `Dockerfile.api`; no `MODEL_API_KEY` set).
- **Checks:**
  - `/api/health` reports `muse_mode: replay`.
  - `POST /api/session {"mode":"live"}` without a code returns **403**.
  - CORS allows only the Vercel origin.
- **e2e against the deployed URLs** (`web/e2e/demo-replay.mjs`, real browser): **26/26 checks** for demo cases A and B, including Verify (SHA-256 match).

### Project-wide Meta API usage (from `fixtures/usage/*.jsonl`)
| Ledger | Calls | Models | Tokens in / out | Audio |
|---|---|---|---|---|
| Phase 0 smoke | 3 | spark, wonder, ASR | small | 6.3 s |
| 1B1 (`1B1.jsonl`) | 2 ASR | ASR | — | 12.7 s |
| 1B2 + first live run (`1B2.jsonl`) | 93 | 90 spark, 3 wonder | 109 k / 37 k | — |
| 2b (`2.jsonl`, `2-asr.jsonl`) | 58 | 48 spark, 10 wonder | 68 k / 33 k | 7.6 s |
| **Total** | **≈ 156** | | **≈ 177 k / 69 k** | **≈ 27 s** |

Meta has not published confirmed per-token prices.
- Even at a pessimistic USD 3 / M input and USD 15 / M output, the total is **under USD 2**, against the USD 40 ceiling.
- Before the cancellation fix, at most 2 timed-out reasoner requests were not ledgered.
- Confirm the exact figure in the Meta console.

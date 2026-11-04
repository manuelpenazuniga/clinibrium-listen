# Deploy — Clinibrium Listen

Research prototype · Not for clinical use · The physician decides.

Two services: the **API** on Railway (`Dockerfile.api`, `railway.json`) and the
**web** on Vercel (`web/`, `web/vercel.json`). This file lists every variable
with **placeholders only**. Never commit real values; the only secret is
`MODEL_API_KEY`, and it lives only in the Railway variables UI.

## Modes and the live gate

| Who | What they get |
|---|---|
| Public visitor (no code) | `replay`: demo cases A and B from `fixtures/replays/**`, fully offline, no microphone, no uploads of their own. Never calls Meta, even on a server with `MUSE_MODE=live`. |
| Holder of `DEMO_ACCESS_CODE`, with `LIVE_AUDIO=1` on the server | A `live` session: microphone, own photos, real Meta calls. |

Enforced on the server (`api/listen/registry.py resolve_mode`):

- `POST /api/session {"mode":"live"}` without `LIVE_AUDIO=1` **and** a matching
  `DEMO_ACCESS_CODE` → **403**. The comparison is constant-time.
- With no `mode`, a session gets `MUSE_MODE`. On a `MUSE_MODE=live` server, a
  client without the code gets `replay`.
- Live audio frames on the WebSocket are dropped unless the session has
  `live_audio_allowed`.
- **Daily caps** (`api/muse/daily_cap.py`, per UTC day, process-wide, persisted
  to `LIVE_CAP_FILE`). When a cap is reached, that live resource is refused
  until the next day; replay keeps working.
  - Live sessions: `LIVE_DAILY_SESSIONS`. Over the cap, `POST /api/session` returns **429**.
  - LLM requests: `LIVE_DAILY_MODEL_CALLS`.
  - ASR streams and push-to-talk requests: `LIVE_DAILY_ASR_STREAMS`.
- On top of the daily caps, the fail-closed per-ledger budgets from 1B1/1B2 still
  apply: `MUSE_MAX_LIVE_CALLS`, `MUSE_MAX_WONDER_CALLS`, `MUSE_MAX_VISION_CALLS`
  and `MUSE_MAX_AUDIO_SECONDS`. If one is unset or 0, live is disabled.

So a leaked access code can spend at most one day's caps, and the budget totals
bound the spend overall.

## API — Railway

Railway builds `Dockerfile.api`. **Set the service variable `RAILWAY_DOCKERFILE_PATH=Dockerfile.api`:** with Railway CLI 5.x the `railway.json` builder setting was not applied, and the first build fell back to Railpack and failed with "No start command detected". `railway.json` still configures the health check at
`GET /api/health`, and runs 1 replica with 1 worker. Sessions live in memory and
the daily cap is per process. The image's defaults are `MUSE_MODE=replay` and
`LIVE_AUDIO=0`.

| Variable | Public (replay) | Live recording session | Notes |
|---|---|---|---|
| `ALLOWED_ORIGINS` | `https://<your-vercel-app>.vercel.app` | same | Comma-separated CORS origins. Required. |
| `MUSE_MODE` | `replay` (image default) | `replay` or `live` | Leave it at `replay`: code holders get live by asking for it. |
| `LIVE_AUDIO` | `0` (image default) | `1` | |
| `DEMO_ACCESS_CODE` | unset | `<long-random-code>` | Share it out of band. Rotate it after the recording. |
| `MODEL_API_KEY` | unset | `<meta-model-api-key>` | **Secret.** Railway variables only. |
| `MUSE_MAX_LIVE_CALLS` | unset | `<total LLM calls, e.g. 150>` | Fail closed if unset or 0. Counted from `MUSE_USAGE_LEDGER`. |
| `MUSE_MAX_WONDER_CALLS` | unset | `<e.g. 30>` | Advocate and red-flag reasoner. |
| `MUSE_MAX_VISION_CALLS` | unset | `<≤ 10>` | The hard cap is 10. |
| `MUSE_MAX_AUDIO_SECONDS` | unset | `<e.g. 900>` | Realtime and push-to-talk audio. |
| `LIVE_DAILY_SESSIONS` | `20` (image default) | `<e.g. 10>` | `0` disables live sessions. |
| `LIVE_DAILY_MODEL_CALLS` | `300` (image default) | `<e.g. 150>` | |
| `LIVE_DAILY_ASR_STREAMS` | `40` (image default) | `<e.g. 20>` | |
| `LIVE_CAP_FILE` | `/tmp/clinibrium/live-cap.json` (image default) | point it at a Railway volume, e.g. `/data/live-cap.json` | Without a volume, a redeploy resets the day's counters; the budgets still hold. |
| `MUSE_USAGE_LEDGER` | `/tmp/clinibrium/usage-llm.jsonl` (image default) | a volume path, e.g. `/data/usage-llm.jsonl` | Counters only: no text, no keys. |
| `MUSE_USAGE_LOG` | `/tmp/clinibrium/usage-asr.jsonl` (image default) | a volume path, e.g. `/data/usage-asr.jsonl` | Counters only. |
| `MUSE_RECORD` | `0` | `0` | Never `1` on a deployment. |
| `PORT` | set by Railway | set by Railway | |

Verify a deployment without spending anything:

```bash
curl -s https://<your-api>.up.railway.app/api/health
```

The response must contain `"muse_mode":"replay"`. A live request without the code must be refused:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://<your-api>.up.railway.app/api/session -H 'content-type: application/json' -d '{"mode":"live"}'
```

It must print `403`.

## Web — Vercel

- **Root Directory: `web/`.** Set this in the Vercel project settings: it is a
  project setting, not a `vercel.json` key. `web/vercel.json` then applies:
  the Next.js framework, `pnpm install --frozen-lockfile`, and `pnpm build`.
- The build reads nothing outside `web/`. These files are committed copies:
  - `lib/field-catalog.json`, from `config/field_catalog.json`;
  - `lib/bench-table.json`, from `bench/results/table.json`;
  - `public/demo-docs/B-meds.png`, the synthetic photo the case-B vision replay was recorded with.

  `pnpm lint` (and so `./check.sh`) fails if a copy is stale. Refresh them with:

  ```bash
  cd web && pnpm sync:catalog && pnpm sync:static
  ```

| Variable | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://<your-api>.up.railway.app` | REST base. If unset, the app runs on the in-browser mock. |
| `NEXT_PUBLIC_API_WS_URL` | `wss://<your-api>.up.railway.app` | WebSocket base. Defaults to the API URL with `http`→`ws`. |
| `NEXT_PUBLIC_MOCK` | unset | `1` forces the in-browser mock (development only). |
| `NEXT_PUBLIC_MOCK_LIVE_AUDIO` | unset | Mock only: shows the microphone button. |

`NEXT_PUBLIC_*` values are baked into the build, so redeploy the web after you change them.
The access code is never a web variable. The clinician types it on the landing page,
and it is sent only in the `POST /api/session` body.

## Pre-deploy checklist

1. `./check.sh` is green.
2. `web/e2e/run-replay.sh` passes. It runs the real API in replay mode and the production web build. See `docs/DEMO_CHECKLIST.md`.
3. Railway: `ALLOWED_ORIGINS` is set to the Vercel URL. For a public deploy, leave `MODEL_API_KEY`, `LIVE_AUDIO` and `DEMO_ACCESS_CODE` unset.
4. Vercel: Root Directory is `web/`, and the two `NEXT_PUBLIC_API_*` variables point at Railway.
5. After a live recording, unset `LIVE_AUDIO`, rotate `DEMO_ACCESS_CODE`, and remove `MODEL_API_KEY`.

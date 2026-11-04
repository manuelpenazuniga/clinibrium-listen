# Clinibrium Listen — web

Next.js 16 + shadcn/ui (base-nova) + the vendored `orb` / `waveform` visual components.
Research prototype · Not for clinical use · The physician decides.

## Run

```bash
pnpm install
NEXT_PUBLIC_MOCK=1 pnpm dev          # fully in-browser, against web/mocks/ (no API needed)
pnpm dev                              # against the API at NEXT_PUBLIC_API_URL / NEXT_PUBLIC_API_WS_URL
```

Mock mode is on when `NEXT_PUBLIC_MOCK=1` **or** `NEXT_PUBLIC_API_URL` is unset.
`NEXT_PUBLIC_MOCK_LIVE_AUDIO=1` makes the mock report `live_audio_allowed=true`, so the
mic button (AudioWorklet) shows instead of "Play demo case".

Gate: `pnpm typecheck && pnpm lint && pnpm build` (plus `./check.sh` at the repo root).

## Screens

| Route | What |
|---|---|
| `/` | Landing: demo cases (`GET /api/demo-cases`) → `POST /api/session {demo_case}` → `/case/{id}?demo=A` |
| `/case/[id]` | Orb + live captions, grouped form (item states), decision card, question card (speechSynthesis), confirmation requests, window clock (only when `state.onset`), document upload, kill switch (header), finalize with blocking items |
| `/case/[id]/summary` | Decision, differential, explanation + cited chunk IDs, deterministic letter (copy/print), receipt + **Verify** (WebCrypto SHA-256 over `receipt.canonical_json`) |
| `/bench` | Table rendered generically from `mocks/bench-table.json` (placeholder for `bench/results/table.json`) |

## Layout

- `lib/contracts.ts` — **generated**, never edit (`scripts/gen_contracts.sh`).
- `lib/protocol.ts` — WS envelopes (SPECS §5.4): client `{type, ...}` messages; server `partial` / `state` / `error`.
- `lib/field-catalog.json` — slim copy of `config/field_catalog.json` (labels, groups, enums). Regenerate with `pnpm sync:catalog`; `node scripts/sync-catalog.mjs --check` detects drift.
- `hooks/use-session.ts` — WS client (real socket or mock), full `SessionState` per message.
- `hooks/use-mic-stream.ts` + `public/pcm16-worklet.js` — mic → 16 kHz mono PCM16, 100 ms (3200-byte) binary frames.
- `hooks/use-demo-player.ts` — "Play demo case": sends the scripted turns as `text_turn`, then answers planner questions from `answers` (works against the mock and a replay-mode server).
- `mocks/` — in-browser WS mock: hand-written `SessionState` patch sequences for cases A and B, small reducers for clinician actions, receipts with SHA-256 precomputed outside the browser.

The UI never computes urgency or actions: it renders `state.result` as sent. The finalize
blocker list is display-only; the server enforces it.

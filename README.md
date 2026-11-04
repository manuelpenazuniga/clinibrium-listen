# Clinibrium Listen

> Voice-first clinical decision support for vertigo in the emergency room.
> The physician dictates. Meta's models listen, structure and ask. Clinibrium's
> deterministic engine makes the safety call. The physician decides.

**Research prototype · Not for clinical use · The physician decides.**
Scripted dictations only — no real patient data.

Status: **Phase 0** (scaffold, engine port, contracts). See [SPECS.md](SPECS.md)
for the full design, [AGENTS.md](AGENTS.md) for contributor rules and
[PROVENANCE.md](PROVENANCE.md) for what was ported vs. built.

## Layout

| Path | |
|---|---|
| `engine/` | Ported deterministic engine (`clinibrium`) + `adapter.py` |
| `api/` | FastAPI (`api/main.py`), contracts, provider interfaces + mocks |
| `web/` | Next.js 16 + shadcn/ui |
| `config/` | Field catalog (generated), protocol windows, referral labels, ASR keywords |
| `bench/`, `fixtures/replays/` | Bench cases and recorded model replays (Phase 1) |
| `scripts/` | Generators (`gen_catalog.py`, `gen_contracts.sh`) and `smoke_meta.py` |

## Run

```bash
uv sync                                   # Python 3.12
uv run uvicorn api.main:app --reload      # API on :8000
cd web && pnpm install && pnpm dev        # web on :3000
./check.sh                                # the gate: ruff, mypy, pytest, typecheck, lint
```

Configuration: copy `.env.example` to `.env`. The only secret is `MODEL_API_KEY`.

## Data handling

The public deployment runs in replay mode with preloaded cases only. Live
sessions (used to record the demo) send scripted audio, text and images to the
Meta Model API.

## License

Apache-2.0 (see [LICENSE](LICENSE) and [NOTICE](NOTICE)).

#!/usr/bin/env bash
# Clinibrium Listen gate (SPECS §0.6: Done = ./check.sh green). Exits 0 on green.
# Python: ruff, mypy, pytest, generated-file freshness. Web: typecheck, lint.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

step() { printf '\n=== %s ===\n' "$*"; }

step "python: sync"
uv sync --frozen --quiet

step "python: ruff"
uv run ruff check .

step "python: mypy"
uv run mypy

step "python: pytest"
uv run pytest -q

step "generated: config/field_catalog.json fresh"
uv run python scripts/gen_catalog.py --check

step "web: install"
(cd web && pnpm install --frozen-lockfile --silent)

step "generated: web/lib/contracts.ts fresh"
./scripts/gen_contracts.sh --check

step "web: typecheck"
(cd web && pnpm typecheck)

step "web: lint"
(cd web && pnpm lint)

printf '\n✓ check.sh green\n'

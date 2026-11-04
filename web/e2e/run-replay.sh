#!/usr/bin/env bash
# E2E: real API (MUSE_MODE=replay, offline) + production web build → demo-replay.mjs.
# Usage (from the repo root):  web/e2e/run-replay.sh
# No live calls: replay serves fixtures/replays/**; nothing is recorded.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_PORT="${E2E_API_PORT:-8000}"
WEB_PORT="${E2E_WEB_PORT:-3000}"
LOG="$ROOT/web/e2e/out"
mkdir -p "$LOG"

# Each server runs in its own process group (setsid) so cleanup also stops the
# children that pnpm / uv spawn (next-server, uvicorn).
cleanup() {
  for pid in "${API_PID:-}" "${WEB_PID:-}"; do
    if [ -n "$pid" ]; then kill -- "-$pid" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT

for port in "$API_PORT" "$WEB_PORT"; do
  if curl -s -o /dev/null "http://localhost:$port"; then
    echo "port $port is already in use; stop that server first" >&2
    exit 1
  fi
done

cd "$ROOT"
setsid env -u MODEL_API_KEY MUSE_MODE=replay MUSE_RECORD=0 LIVE_AUDIO=0 \
  ALLOWED_ORIGINS="http://localhost:$WEB_PORT" \
  uv run uvicorn api.main:app --host 127.0.0.1 --port "$API_PORT" >"$LOG/api.log" 2>&1 &
API_PID=$!

cd "$ROOT/web"
NEXT_PUBLIC_API_URL="http://localhost:$API_PORT" NEXT_PUBLIC_API_WS_URL="ws://localhost:$API_PORT" \
  pnpm build >"$LOG/web-build.log" 2>&1
NEXT_PUBLIC_API_URL="http://localhost:$API_PORT" NEXT_PUBLIC_API_WS_URL="ws://localhost:$API_PORT" \
  setsid pnpm start -p "$WEB_PORT" >"$LOG/web.log" 2>&1 &
WEB_PID=$!

for _ in $(seq 1 60); do
  curl -sf "http://localhost:$API_PORT/api/health" >/dev/null && curl -sf "http://localhost:$WEB_PORT" >/dev/null && break
  sleep 1
done
curl -s "http://localhost:$API_PORT/api/health"; echo

E2E_WEB_URL="http://localhost:$WEB_PORT" E2E_API_WS_URL="ws://localhost:$API_PORT" node e2e/demo-replay.mjs

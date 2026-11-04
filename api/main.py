"""Clinibrium Listen API — Phase 0 skeleton (SPECS §5.4).

Endpoints now: `GET /api/health`, `GET /api/demo-cases`, `WS /ws/session/{id}` (echo).
Workstream 1A replaces the WS echo with `api/listen/ws.py` + `routes.py`.

Run:  uv run uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# The engine package lives in engine/ (SPECS §4); make it importable when the
# API is started from the repo root without PYTHONPATH (uvicorn, Railway).
_ENGINE = str(Path(__file__).resolve().parents[1] / "engine")
if _ENGINE not in sys.path:
    sys.path.insert(0, _ENGINE)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from adapter import engine_version  # noqa: E402
from api.catalog import load_catalog  # noqa: E402
from api.demo_cases import load_demo_cases  # noqa: E402

DISCLAIMER = "Research prototype · Not for clinical use · The physician decides."


def _allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app() -> FastAPI:
    app = FastAPI(title="Clinibrium Listen API", version="0.1.0", description=DISCLAIMER)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "engine_version": engine_version(),
            "muse_mode": os.environ.get("MUSE_MODE", "mock"),
            "catalog_keys": len(load_catalog().fields),
            "disclaimer": DISCLAIMER,
        }

    @app.get("/api/demo-cases")
    def demo_cases() -> list[dict[str, Any]]:
        return load_demo_cases()

    @app.websocket("/ws/session/{session_id}")
    async def ws_session(ws: WebSocket, session_id: str) -> None:
        """Phase 0 echo: JSON frames come back as `{"type":"echo",...}`,
        binary frames as `{"type":"echo_bytes","n":<len>}`."""
        await ws.accept()
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    await ws.send_json({"type": "echo_bytes", "session_id": session_id,
                                        "n": len(msg["bytes"])})
                elif msg.get("text") is not None:
                    await ws.send_json({"type": "echo", "session_id": session_id,
                                        "text": msg["text"]})
        except WebSocketDisconnect:
            pass

    return app


app = create_app()

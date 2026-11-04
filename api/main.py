"""Clinibrium Listen API (SPECS §5.4).

Endpoints: `GET /api/health`, `GET /api/demo-cases`, `POST /api/session`,
`POST /api/session/{id}/document`, `GET /api/session/{id}/receipt`,
`WS /ws/session/{id}` (api/listen/routes.py + api/listen/ws.py).

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

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from adapter import engine_version  # noqa: E402
from api.catalog import load_catalog  # noqa: E402
from api.demo_cases import load_demo_cases  # noqa: E402
from api.listen import routes, ws  # noqa: E402

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

    app.include_router(routes.router)
    app.include_router(ws.router)
    return app


app = create_app()

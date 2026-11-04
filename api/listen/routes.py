"""REST endpoints (SPECS §5.4): session creation, document upload, receipt."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from api.listen import registry
from api.listen.session import Session

router = APIRouter()

MAX_DOCUMENT_BYTES = 8 * 1024 * 1024


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str | None = None
    demo_case: str | None = None
    access_code: str | None = None


def _session(session_id: str) -> Session:
    s = registry.SESSIONS.get(session_id)
    if s is None:
        raise HTTPException(404, "unknown session")
    return s


@router.post("/api/session")
async def create_session(body: CreateSession | None = None,
                         x_demo_access_code: str | None = Header(default=None),
                         ) -> dict[str, Any]:
    body = body or CreateSession()
    try:
        s = registry.create(body.mode, body.demo_case, body.access_code or x_demo_access_code)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, f"bad session request: {exc}") from exc
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    return {"session_id": s.state.session_id, "state": s.state.model_dump(mode="json")}


@router.post("/api/session/{session_id}/document")
async def upload_document(session_id: str, file: UploadFile = File(...),
                          document_id: str | None = Form(default=None)) -> dict[str, Any]:
    s = _session(session_id)
    if s.providers.mode == "live" and not s.state.live_audio_allowed:
        raise HTTPException(403, "uploads require LIVE_AUDIO=1 and a valid access code")
    data = await file.read()
    if not data or len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(413, "empty or too large document")
    doc_id = document_id or f"doc-{uuid.uuid4().hex[:8]}"
    await s.document(data, file.content_type or "application/octet-stream", doc_id)
    return {"document_id": doc_id, "status": "queued"}


@router.get("/api/session/{session_id}/receipt")
async def get_receipt(session_id: str) -> dict[str, Any]:
    s = _session(session_id)
    if s.state.receipt is None:
        raise HTTPException(409, "case not finalized")
    return s.state.receipt.model_dump(mode="json")


__all__ = ["router"]

"""WebSocket `/ws/session/{id}` (SPECS §5.4).

Client → server: binary PCM16 frames (only when `live_audio_allowed` and Muse
is on) and JSON control messages, forwarded to the session's single writer.
Server → client: `state` (full snapshot on every change), `partial`, `error`.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.listen import registry
from api.listen.session import Session
from api.muse.interfaces import AsrStream

router = APIRouter()

CLIENT_TYPES = frozenset({
    "confirm", "reject", "confirm_all", "edit", "resolve_conflict", "skip_question",
    "resolve_confirmation", "text_turn", "kill_switch", "finalize", "stop_audio",
})


class AsrBridge:
    """One live ASR stream: audio in, partial/final events → the session."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.stream: AsrStream = session.providers.open_asr()
        self.task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        try:
            async for ev in self.stream.events():
                if ev.kind == "partial":
                    await self.session.submit("partial", ev.text)
                elif ev.kind == "final" and ev.text.strip():
                    await self.session.text_turn(ev.text, ev.start_ms, ev.end_ms)
                elif ev.kind == "error":
                    await self.session.submit("error", "asr", ev.error_code or "error")
        except Exception as exc:  # the stream died; the client may push-to-talk
            await self.session.submit("error", "asr", type(exc).__name__)

    async def feed(self, pcm: bytes) -> None:
        await self.stream.feed(pcm)

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self.stream.close()
        self.task.cancel()


async def _sender(ws: WebSocket, q: asyncio.Queue[dict[str, Any]]) -> None:
    while True:
        await ws.send_json(await q.get())


@router.websocket("/ws/session/{session_id}")
async def ws_session(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    session = registry.get_or_create(session_id, ws.query_params.get("access_code"))
    out = session.subscribe()
    sender = asyncio.create_task(_sender(ws, out))
    asr: AsrBridge | None = None
    warned_audio = False

    async def stop_asr() -> None:
        nonlocal asr
        if asr is not None:
            await asr.close()
            asr = None

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                st = session.state
                if not st.live_audio_allowed or not st.muse_enabled or st.phase != "live":
                    if not warned_audio:
                        warned_audio = True
                        out.put_nowait({"type": "error", "code": "live_audio_not_allowed",
                                        "message": "live audio is disabled for this session"})
                    continue
                if asr is None:
                    asr = AsrBridge(session)
                await asr.feed(msg["bytes"])
                continue
            text = msg.get("text")
            if text is None:
                continue
            try:
                data = json.loads(text)
                if not isinstance(data, dict) or data.get("type") not in CLIENT_TYPES:
                    raise ValueError("unknown message")
            except ValueError:
                out.put_nowait({"type": "error", "code": "bad_message",
                                "message": "expected a JSON control message"})
                continue
            if data["type"] == "stop_audio" or (data["type"] == "kill_switch" and data.get("on")):
                await stop_asr()
            await session.client(data)
    except WebSocketDisconnect:
        pass
    finally:
        await stop_asr()
        session.unsubscribe(out)
        sender.cancel()


__all__ = ["router"]

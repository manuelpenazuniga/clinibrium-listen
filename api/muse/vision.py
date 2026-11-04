"""Live document reader (muse-spark-1.3 vision): image → `VisionOut`.

Deltas are always proposals (the session marks them `source=document`);
`read_text` is the evidence source, so each delta's quote must appear in it.
"""
from __future__ import annotations

import base64
import hashlib

from api.catalog import normalize
from api.listen.contracts import VisionOut
from api.muse.client import SPARK, MuseClient, MuseError, load_prompt
from api.muse.extractor import check_keys, key_spec, sanitize_deltas
from api.muse.interfaces import VisionCtx

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class LiveVision:
    def __init__(self, client: MuseClient) -> None:
        self.client = client

    async def read(self, image: bytes, mime: str, ctx: VisionCtx) -> VisionOut:
        check_keys(ctx.catalog_keys)
        if mime not in ALLOWED_MIME:
            raise MuseError(f"vision: unsupported mime {mime!r}")
        if not image or len(image) > MAX_IMAGE_BYTES:
            raise MuseError("vision: empty or oversized image")
        url = f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"
        out = await self.client.complete(
            role="vision", model=SPARK, system=load_prompt("vision"),
            user={"keys": key_spec(ctx.catalog_keys)}, out=VisionOut,
            key_inputs={"image_sha256": hashlib.sha256(image).hexdigest(), "mime": mime},
            prompt_name="vision", image_data_url=url)
        text = normalize(out.read_text)
        deltas = [d for d in sanitize_deltas(out.deltas, ctx.catalog_keys)
                  if normalize(d.quote) in text]
        return VisionOut(deltas=[d.model_copy(update={"answers_question_id": None})
                                 for d in deltas], read_text=out.read_text)

"""Live phraser (muse-spark-1.3): `QuestionDraft` → one short ES/EN question."""
from __future__ import annotations

from api.listen.contracts import PhrasingOut
from api.muse.client import SPARK, MuseClient, MuseError, load_prompt
from api.muse.extractor import check_keys
from api.muse.interfaces import QuestionDraft

MAX_CHARS = 240


class LivePhraser:
    def __init__(self, client: MuseClient) -> None:
        self.client = client

    async def phrase(self, q: QuestionDraft) -> PhrasingOut:
        check_keys([q.key])
        user = {"key": q.key, "label_es": q.label_es, "label_en": q.label_en,
                "enum_values": q.enum_values, "enum_labels_es": q.enum_labels_es,
                "reason": q.reason}
        out = await self.client.complete(
            role="phraser", model=SPARK, system=load_prompt("phrasing"), user=user,
            out=PhrasingOut, key_inputs={"key": q.key, "enum_values": q.enum_values},
            prompt_name="phrasing")
        es, en = out.text_es.strip(), out.text_en.strip()
        if not es or not en:
            raise MuseError("phraser: empty question")
        return PhrasingOut(text_es=es[:MAX_CHARS], text_en=en[:MAX_CHARS])

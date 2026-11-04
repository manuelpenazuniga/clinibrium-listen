"""Live reasoner: explains the engine result; cites only delivered chunk IDs.

`pick_reasoner` = Wonder if a red flag is shown, else Spark (SPECS §7).
The model's `suggested_urgency` is advisory text only; it never reaches the
decision (L3) — the session ignores it for urgency.
"""
from __future__ import annotations

from api.listen.contracts import EngineResultView, ReasonerOut
from api.muse.client import SPARK, WONDER, MuseClient, load_prompt
from api.muse.extractor import check_keys
from api.muse.interfaces import Providers, Reasoner, ReasonerCtx

MAX_STEPS = 4


def pick_model(result: EngineResultView) -> str:
    return WONDER if result.red_flags else SPARK


def pick_reasoner(providers: Providers, result: EngineResultView) -> Reasoner:
    return providers.reasoner_wonder if result.red_flags else providers.reasoner_spark


class LiveReasoner:
    def __init__(self, client: MuseClient, model_id: str) -> None:
        self.client = client
        self.model_id = model_id

    async def explain(self, ctx: ReasonerCtx) -> ReasonerOut:
        check_keys(list(ctx.confirmed_values))
        r = ctx.result
        result = {
            "urgency": r.urgency,
            "red_flags": [{"id": f.id, "label": f.label} for f in r.red_flags],
            "differential": [{"diagnosis": d.diagnosis, "score_pct": d.score_pct}
                             for d in r.differential[:5]],
            "forced_actions": r.forced_actions, "blocked_actions": r.blocked_actions,
        }
        user = {
            "lang": ctx.lang,
            "confirmed_values": {k: ctx.confirmed_values[k] for k in sorted(ctx.confirmed_values)},
            "result": result,
            "grounding": [{"chunk_id": c.chunk_id, "text": c.text} for c in ctx.grounding],
        }
        key_inputs = {"urgency": r.urgency, "red_flags": sorted(f.id for f in r.red_flags),
                      "top1": r.differential[0].diagnosis if r.differential else None,
                      "lang": ctx.lang}
        out = await self.client.complete(
            role="reasoner", model=self.model_id, system=load_prompt("reasoner"), user=user,
            out=ReasonerOut, key_inputs=key_inputs, prompt_name="reasoner")
        delivered = {c.chunk_id for c in ctx.grounding}
        cited = [c for c in dict.fromkeys(out.cited_chunk_ids) if c in delivered]
        return out.model_copy(update={
            "cited_chunk_ids": cited,
            "suggested_next_steps": [s for s in out.suggested_next_steps if s.strip()][:MAX_STEPS],
        })

"""Live stroke advocate (muse-wonder-1.0): may only ADD confirmation requests.

Sanitation: only alert keys from the allowlist, never a key already in the
form, exactly one correctly typed value slot, and a quote that is a verbatim
(normalized) substring of a dictated turn. Urgency/actions are never touched.
"""
from __future__ import annotations

from api.catalog import load_catalog, normalize
from api.listen.contracts import AdvocateItemOut, AdvocateOut
from api.muse.client import WONDER, MuseClient, load_prompt
from api.muse.extractor import _slot_ok, check_keys, key_spec
from api.muse.interfaces import AdvocateCtx
from api.muse.mock import ADVOCATE_ALERT_KEYS


def sanitize_requests(items: list[AdvocateItemOut], ctx: AdvocateCtx,
                      allowed: list[str]) -> list[AdvocateItemOut]:
    cat = load_catalog()
    turns = [normalize(t.text) for t in ctx.turns]
    out: dict[str, AdvocateItemOut] = {}
    for r in items:
        if r.key not in allowed or r.key in ctx.current_values or r.key in out:
            continue
        if not _slot_ok(cat.get(r.key), r.value_bool, r.value_int, r.value_enum, r.value_text):
            continue
        q = normalize(r.quote)
        if not q or not any(q in t for t in turns):
            continue
        out[r.key] = r
    return list(out.values())


class LiveAdvocate:
    def __init__(self, client: MuseClient) -> None:
        self.client = client

    async def review(self, ctx: AdvocateCtx) -> AdvocateOut:
        check_keys(ctx.catalog_keys)
        check_keys(list(ctx.current_values))
        allowed = [k for k in ADVOCATE_ALERT_KEYS if k in ctx.catalog_keys]
        if not ctx.turns or not allowed:
            return AdvocateOut(requests=[])
        r = ctx.result
        user = {
            "keys": key_spec(allowed),
            "turns": [t.text for t in ctx.turns],
            "current_values": {k: ctx.current_values[k] for k in sorted(ctx.current_values)},
            "result": ({"urgency": r.urgency, "red_flags": [f.id for f in r.red_flags]}
                       if r else None),
        }
        # Output is filtered against current_values afterwards, so the key holds
        # only the dictation itself.
        out = await self.client.complete(
            role="advocate", model=WONDER, system=load_prompt("advocate"), user=user,
            out=AdvocateOut, key_inputs={"turns": [t.text for t in ctx.turns]},
            prompt_name="advocate")
        return AdvocateOut(requests=sanitize_requests(out.requests, ctx, allowed))

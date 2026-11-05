"""MUSE_MODE=replay: serve recorded Meta responses by replay key — no network.

Recordings live in `fixtures/replays/<case>/<replay_key>.json` (written by
`api.muse.client.record_exchange` when `MUSE_RECORD=1`). The key is the SHA-256
of role + model + prompt hash + the role's semantic inputs (see
`api.muse.client.replay_key`). A request with no recording raises `ReplayMiss`
(fails loudly; never falls back to the network or the mock).

ASR in replay mode is the scripted mock stream (demo-case timing).

Recording the demo cases (live, budget-guarded, run once):
    MUSE_RECORD=1 MUSE_MAX_LIVE_CALLS=… MUSE_MAX_WONDER_CALLS=… \
        uv run python -m api.muse.replay record [--only A,B,A-en,B-en,phrasing]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# `python -m api.muse.replay record` needs the engine (`adapter`, `clinibrium`)
# importable without PYTHONPATH=engine:. (same approach as scripts/asr_probe.py).
_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api.muse.client import (  # noqa: E402
    REPLAYS_DIR,
    ChatRequest,
    ChatResult,
    Lang,
    ReplayMiss,
    build_with_transport,
)
from api.muse.interfaces import Providers  # noqa: E402


def _index(root: str) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in sorted(Path(root).glob("*/*.json")):
        out[p.stem] = p
    return out


class ReplayTransport:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or REPLAYS_DIR

    def lookup(self, key: str) -> dict[str, Any] | None:
        path = _index(str(self.root)).get(key)
        if path is None:
            return None
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data

    async def send(self, req: ChatRequest) -> ChatResult:
        data = None
        for key in (req.replay_key, *req.alt_replay_keys):
            data = self.lookup(key)
            if data is not None:
                break
        if data is None:
            raise ReplayMiss(f"no replay for role={req.role} model={req.model} "
                             f"key={req.replay_key} under {self.root}")
        if data.get("role") != req.role or data.get("model") != req.model:
            raise ReplayMiss(f"replay {data.get('replay_key')} is for {data.get('role')}/"
                             f"{data.get('model')}, not {req.role}/{req.model}")
        resp = data["response"]
        return ChatResult(content=resp["content"], usage=resp.get("usage", {}),
                          latency_ms=int(resp.get("latency_ms", 0)))


def build_providers(lang: Lang = "es") -> Providers:
    """MUSE_MODE=replay provider bundle (api.muse.interfaces.get_providers)."""
    providers: Providers = build_with_transport("replay", ReplayTransport(), lang)
    return providers


# ---------------------------------------------------------------- recording

DEMO_IMAGE = REPLAYS_DIR / "B" / "B-meds.png"


def _project(fields: dict[str, Any]) -> Any:
    """Minimal atomic-fields → CaseFeatures projection, used only to build the
    recording contexts (the session uses api/listen/policy.project)."""
    from clinibrium.contracts.features import CaseFeatures

    data: dict[str, Any] = {}
    sets: dict[str, list[str]] = {}
    for k, v in fields.items():
        if k.startswith("context."):
            continue
        if "." in k:
            base, item = k.split(".", 1)
            if v is True:
                sets.setdefault(base, []).append(item)
        else:
            data[k] = v
    data.update({k: set(v) for k, v in sets.items()})
    return CaseFeatures.model_validate(data)


def _result_view(fields: dict[str, Any]) -> Any:
    from adapter import evaluate
    from api.catalog import load_config
    from api.listen.contracts import DxView, EngineResultView, RedFlagHitView

    r = evaluate(_project(fields))
    urg = r.urgency.value
    labels = load_config("referral_labels.json")[urg]
    return EngineResultView(
        urgency=urg, source_eval="confirmed",
        red_flags=[RedFlagHitView(id=h.id, label=h.label, severity=h.severity,
                                  provisional=False) for h in r.red_flag.hits],
        differential=[DxView(diagnosis=c.diagnosis.value, score_pct=round(c.score * 100),
                             provisional=False) for c in r.differential.candidates],
        forced_actions=sorted(a.value for a in r.forced_actions),
        blocked_actions=sorted(r.blocked_actions), applied_rails=list(r.applied_rails),
        advocate_floor_active=False, referral_label_es=labels["label_es"],
        referral_label_en=labels["label_en"], engine_version=r.engine_version), r


def _grounding(engine_result: Any, fields: dict[str, Any]) -> list[Any]:
    from api.muse.interfaces import GroundingChunkView
    from clinibrium.grounding.inline import InlineGrounding

    chunks = InlineGrounding().retrieve(engine_result.differential, _project(fields), k=4)
    return [GroundingChunkView(chunk_id=c.source_id, text=c.text) for c in chunks]


def _values(deltas: list[Any]) -> dict[str, Any]:
    return {d.key: next(v for v in (d.value_bool, d.value_int, d.value_enum, d.value_text)
                        if v is not None) for d in deltas}


async def _record_case(p: Providers, case: dict[str, Any]) -> list[str]:
    from api.catalog import load_catalog
    from api.listen.contracts import Question, Turn
    from api.muse.interfaces import AdvocateCtx, ExtractCtx, ReasonerCtx, VisionCtx
    from api.muse.reasoner import pick_reasoner

    os.environ["MUSE_REPLAY_CASE"] = case["id"]
    keys = load_catalog().keys
    log: list[str] = []
    turns: list[Turn] = [Turn(**t) for t in case["turns"]]
    values: dict[str, Any] = {}
    seen: list[Turn] = []
    for t in turns:
        seen.append(t)
        out = await p.extractor.extract(ExtractCtx(
            turns=list(seen), new_turn=t, catalog_keys=keys, current_values=dict(values),
            pending_question=None))
        values.update(_values(out.deltas))
        log.append(f"{case['id']} extractor turn {t.turn_id}: {sorted(_values(out.deltas))}")
    for n, (qkey, answer) in enumerate(case["answers"].items()):
        last = seen[-1]
        t = Turn(turn_id=last.turn_id + 1, start_ms=last.end_ms + 800,
                 end_ms=last.end_ms + 4000, text=answer)
        seen.append(t)
        q = Question(id=f"q{n + 1}", key=qkey, text_es="", text_en="", reason="", impact=10,
                     status="pending")
        out = await p.extractor.extract(ExtractCtx(
            turns=list(seen), new_turn=t, catalog_keys=keys, current_values=dict(values),
            pending_question=q))
        values.update(_values(out.deltas))
        log.append(f"{case['id']} extractor answer {qkey}: {_values(out.deltas)}")
    adv = await p.advocate.review(AdvocateCtx(turns=list(seen), current_values={},
                                              catalog_keys=keys, result=None))
    log.append(f"{case['id']} advocate: {[r.key for r in adv.requests]}")
    for doc in case["documents"]:
        if DEMO_IMAGE.exists() and doc["id"] == "B-meds":
            vis = await p.vision.read(DEMO_IMAGE.read_bytes(), "image/png",
                                      VisionCtx(document_id=doc["id"], catalog_keys=keys))
            log.append(f"{case['id']} vision: {_values(vis.deltas)}")
    view, engine_result = _result_view(case["gold"]["fields"])
    reasoner = pick_reasoner(p, view)
    confirmed = {k: v for k, v in case["gold"]["fields"].items()}
    expl = await reasoner.explain(ReasonerCtx(
        confirmed_values=confirmed, result=view,
        grounding=_grounding(engine_result, case["gold"]["fields"]),
        lang=case.get("lang", "es")))
    log.append(f"{case['id']} reasoner[{reasoner.model_id}] cites {expl.cited_chunk_ids}")
    return log


async def _record_phrasing(p: Providers) -> list[str]:
    from api.catalog import load_catalog
    from api.muse.interfaces import QuestionDraft

    os.environ["MUSE_REPLAY_CASE"] = "phrasing"
    log: list[str] = []
    for f in load_catalog().fields:
        if not f.askable:
            continue
        out = await p.phraser.phrase(QuestionDraft(
            id=f"q-{f.key}", key=f.key, label_es=f.label_es, label_en=f.label_en,
            enum_values=f.enum_values, enum_labels_es=f.enum_labels_es, reason=""))
        log.append(f"phrasing {f.key}: {out.text_es}")
    return log


async def record(only: set[str]) -> None:
    from api.demo_cases import BUILTIN_DEMO_CASES, ENGLISH_DEMO_CASES
    from api.muse.client import LiveTransport

    if os.environ.get("MUSE_RECORD") != "1":
        sys.exit("set MUSE_RECORD=1 to record")
    replay = ReplayTransport()
    live = LiveTransport()

    class SkipRecorded:
        """Only call live for requests that have no recording yet (no re-recording)."""

        async def send(self, req: ChatRequest) -> ChatResult:
            hit = replay.lookup(req.replay_key)
            if hit is not None:
                r = hit["response"]
                return ChatResult(content=r["content"], usage=r.get("usage", {}))
            return await live.send(req)

    for case in [*BUILTIN_DEMO_CASES, *ENGLISH_DEMO_CASES]:
        if case["id"] in only:
            p = build_with_transport("live", SkipRecorded(), case.get("lang", "es"))
            for line in await _record_case(p, case):
                print(line)
    if "phrasing" in only:
        for line in await _record_phrasing(p):
            print(line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["record"])
    ap.add_argument("--only", default="A,B,phrasing")
    args = ap.parse_args()
    asyncio.run(record(set(args.only.split(","))))


if __name__ == "__main__":
    main()

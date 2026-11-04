"""Per-case orchestrator (SPECS §3, §6, §7 session.py).

Single writer: every mutation of `SessionState` happens in ONE worker task
that consumes an asyncio queue of commands. Model calls never run in that
task; they go to a sequential model lane and come back as `result` commands
tagged with the epoch at dispatch. A result whose epoch is stale (kill switch,
finalize) is discarded (L10); a phrasing result for a question that is no
longer pending is discarded too (superseded).

Final turn pipeline: redact → short-answer check → extractor → evidence →
policy (merge) → conservative evaluation → planner → phraser → push state.
Advocate every 3 turns. Finalize per SPECS §6.4.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.catalog import load_catalog
from api.listen import egress, policy
from api.listen.contracts import (
    AdvocateOut,
    ConfirmationRequest,
    DeltaOut,
    Evidence,
    ExtractorOut,
    FieldState,
    PhrasingOut,
    Question,
    ReasonerOut,
    ReasonerView,
    SessionState,
    Turn,
    VisionOut,
)
from api.listen.evidence import (
    classify_short_answer,
    delta_value,
    quote_in,
    short_answer_value,
    supports,
    validate_delta,
)
from api.listen.letter import build_letter
from api.listen.onset import compute_onset
from api.listen.planner import plan, procedure_keys, to_question
from api.listen.receipt import build_receipt
from api.listen.redact import redact
from api.muse.interfaces import GroundingChunkView, Providers
from clinibrium.grounding.factory import get_grounding

log = logging.getLogger("clinibrium.listen.session")

MODEL_TIMEOUT_S = 12.0
ADVOCATE_EVERY_TURNS = 3
MAX_ERRORS = 20
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "muse" / "prompts"


def utcnow() -> datetime:
    return datetime.now(UTC)


def prompt_hashes() -> dict[str, str]:
    """sha256 of every prompt file (goes into the receipt)."""
    if not PROMPTS_DIR.is_dir():
        return {}
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(PROMPTS_DIR.glob("*.md"))}


@dataclass
class _Job:
    epoch: int
    kind: str  # extract | phrase | advocate | vision
    run: Callable[[], Awaitable[Any]]
    meta: dict[str, Any] = field(default_factory=dict)


class Session:
    def __init__(self, session_id: str, providers: Providers, *,
                 live_audio_allowed: bool = False,
                 clock: Callable[[], datetime] = utcnow,
                 model_timeout_s: float = MODEL_TIMEOUT_S) -> None:
        self.providers = providers
        self.clock = clock
        self.timeout = model_timeout_s
        self._t0 = clock()
        self.state = SessionState(
            session_id=session_id, started_at=self._t0.isoformat(timespec="seconds"),
            epoch=0, snapshot=0, phase="live", muse_enabled=True,
            live_audio_allowed=live_audio_allowed, turns=[], partial=None, fields={},
            questions=[], confirmations=[], onset=None, result=None, reasoning=None,
            letter=None, receipt=None, errors=[])
        self.clinician = policy.ClinicianLog()
        self.drop_log: list[str] = []
        self.discarded: list[str] = []  # stale model results (L10 audit)
        self._eval: policy.Evaluation | None = None
        self._q: asyncio.Queue[tuple[Any, ...]] = asyncio.Queue()
        self._model_q: asyncio.Queue[_Job] = asyncio.Queue()
        self._listeners: set[asyncio.Queue[dict[str, Any]]] = set()
        self._tasks: list[asyncio.Task[None]] = []
        self._final_task: asyncio.Task[None] | None = None
        self._extracting = 0
        self._refresh(bump=False)

    # ------------------------------------------------------------ plumbing

    def _ensure_started(self) -> None:
        if not self._tasks:
            self._tasks = [asyncio.create_task(self._worker()),
                           asyncio.create_task(self._model_lane())]

    async def submit(self, *cmd: Any) -> None:
        self._ensure_started()
        await self._q.put(cmd)

    async def client(self, msg: dict[str, Any]) -> None:
        """A JSON message from the client (SPECS §5.4)."""
        await self.submit("client", msg)

    async def text_turn(self, text: str, start_ms: int | None = None,
                        end_ms: int | None = None) -> None:
        await self.submit("turn", text, start_ms, end_ms)

    async def drain(self) -> None:
        """Wait until every queued command and model job has been processed."""
        self._ensure_started()
        while True:
            await self._q.join()
            await self._model_q.join()
            if self._final_task is not None and not self._final_task.done():
                await self._final_task
                continue
            if self._q.empty() and self._model_q.empty():
                return

    async def close(self) -> None:
        for t in [*self._tasks, *([self._final_task] if self._final_task else [])]:
            t.cancel()
        self._tasks = []

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._listeners.add(q)
        q.put_nowait(self._state_msg())
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._listeners.discard(q)

    def _state_msg(self) -> dict[str, Any]:
        return {"type": "state", "state": self.state.model_dump(mode="json")}

    def _broadcast(self, msg: dict[str, Any]) -> None:
        for q in self._listeners:
            q.put_nowait(msg)

    def _error(self, code: str, message: str) -> None:
        self.state.errors = [*self.state.errors, f"{code}: {message}"][-MAX_ERRORS:]
        self._broadcast({"type": "error", "code": code, "message": message})

    def _now_ms(self) -> int:
        return max(0, int((self.clock() - self._t0).total_seconds() * 1000))

    async def _worker(self) -> None:
        while True:
            cmd = await self._q.get()
            try:
                await self._handle(cmd)
            except Exception as exc:  # never kill the single writer
                log.exception("session command failed")
                self._error("internal", type(exc).__name__)
            finally:
                self._q.task_done()

    async def _model_lane(self) -> None:
        """Sequential model calls; ALWAYS reports back (even when skipped)."""
        while True:
            job = await self._model_q.get()
            out: Any = None
            err: str | None = None
            try:
                if job.epoch != self.state.epoch:
                    err = "stale"
                else:
                    try:
                        out = await asyncio.wait_for(job.run(), self.timeout)
                    except Exception as exc:  # timeout or provider failure
                        err = type(exc).__name__ or "error"
                await self._q.put(("result", job, out, err))
            finally:
                self._model_q.task_done()

    def _dispatch(self, kind: str, run: Callable[[], Awaitable[Any]], **meta: Any) -> None:
        if not self.state.muse_enabled:
            return
        if kind == "extract":
            self._extracting += 1
        self._model_q.put_nowait(_Job(self.state.epoch, kind, run, meta))

    # ------------------------------------------------------------ dispatch

    async def _handle(self, cmd: tuple[Any, ...]) -> None:
        kind = cmd[0]
        if kind == "turn":
            self._on_turn(cmd[1], cmd[2], cmd[3])
        elif kind == "partial":
            self.state.partial = str(cmd[1])
            self._broadcast({"type": "partial", "text": self.state.partial})
        elif kind == "document":
            self._on_document(cmd[1], cmd[2], cmd[3])
        elif kind == "result":
            self._on_result(cmd[1], cmd[2], cmd[3])
        elif kind == "final":
            self._on_final(cmd[1], cmd[2], cmd[3])
        elif kind == "client":
            self._on_client(cmd[1])
        elif kind == "error":
            self._error(str(cmd[1]), str(cmd[2]))

    # --------------------------------------------------------------- turns

    def _on_turn(self, text: str, start_ms: int | None, end_ms: int | None) -> None:
        if self.state.phase == "finalized":
            self._error("finalized", "case is finalized")
            return
        text = redact(str(text)).strip()
        if not text:
            return
        prev_end = self.state.turns[-1].end_ms if self.state.turns else 0
        s = start_ms if isinstance(start_ms, int) else prev_end
        e = end_ms if isinstance(end_ms, int) else max(s, self._now_ms())
        turn = Turn(turn_id=len(self.state.turns) + 1, start_ms=s, end_ms=e, text=text)
        self.state.turns.append(turn)
        self.state.partial = None

        handled: set[str] = set()
        pending = self._pending_question()
        if pending is not None:
            answer = classify_short_answer(text)
            f = load_catalog().get(pending.key)
            if answer == "skip":
                pending.status = "skipped"
                handled |= set(procedure_keys(pending.key))
            elif answer is not None:
                value = short_answer_value(answer, f)
                if value is not None:
                    ev = Evidence(source="answered", quote=text, turn_id=turn.turn_id,
                                  start_ms=turn.start_ms, document_id=None, confidence_pct=100)
                    policy.merge(self.state.fields, policy.new_field(pending.key, value, ev))
                    pending.status = "answered"
                    handled.add(pending.key)

        still_pending = self._pending_question()
        ctx = egress.extract_ctx(self.state.turns[:-1], turn,
                                 policy.current_values(self.state.fields), still_pending)
        extractor = self.providers.extractor
        self._dispatch("extract", lambda: extractor.extract(ctx), turn_id=turn.turn_id,
                       skip_keys=handled)
        self._refresh()

    def _pending_question(self) -> Question | None:
        return next((q for q in self.state.questions if q.status == "pending"), None)

    # ------------------------------------------------------------- results

    def _on_result(self, job: _Job, out: Any, err: str | None) -> None:
        if job.kind == "extract":
            self._extracting = max(0, self._extracting - 1)
        stale = job.epoch != self.state.epoch or err == "stale"
        if stale or (self.state.phase == "finalized" and job.kind != "final"):
            self.discarded.append(f"{job.kind}@epoch{job.epoch}")
            if job.kind == "extract":
                self._refresh()
            return
        if err is not None:
            self._error(f"{job.kind}_unavailable", err)
            self._refresh()
            return
        if job.kind == "extract" and isinstance(out, ExtractorOut):
            self._apply_deltas(out.deltas, job.meta["turn_id"], job.meta["skip_keys"])
        elif job.kind == "vision" and isinstance(out, VisionOut):
            self._apply_document(out, job.meta["document_id"])
        elif job.kind == "phrase" and isinstance(out, PhrasingOut):
            q = next((q for q in self.state.questions if q.id == job.meta["question_id"]), None)
            if q is None or q.status != "pending":
                self.discarded.append(f"phrase:{job.meta['question_id']}:superseded")
                return
            q.text_es, q.text_en = out.text_es, out.text_en
        elif job.kind == "advocate" and isinstance(out, AdvocateOut):
            self._apply_advocate(out)
        if job.kind == "extract" and job.meta["turn_id"] % ADVOCATE_EVERY_TURNS == 0:
            self._dispatch_advocate()
        self._refresh()

    def _apply_deltas(self, deltas: list[DeltaOut], turn_id: int, skip: set[str]) -> None:
        turn = next(t for t in self.state.turns if t.turn_id == turn_id)
        sources = [t.text for t in self.state.turns]
        pending = self._pending_question()
        for d in deltas:
            if d.key in skip:
                self.drop_log.append(f"{d.key}: handled by short answer")
                continue
            acc = validate_delta(d, sources)
            if isinstance(acc, str):
                self.drop_log.append(acc)
                log.info("delta dropped: %s", acc)
                continue
            answers = pending is not None and (
                acc.answers_question_id == pending.id or acc.key in procedure_keys(pending.key))
            ev = Evidence(source="answered" if answers else "dictated", quote=acc.quote,
                          turn_id=turn.turn_id, start_ms=turn.start_ms, document_id=None,
                          confidence_pct=acc.confidence_pct)
            policy.merge(self.state.fields, policy.new_field(acc.key, acc.value, ev))

    def _apply_document(self, out: VisionOut, document_id: str) -> None:
        read_text = redact(out.read_text)
        for d in out.deltas:
            d = d.model_copy(update={"quote": redact(d.quote)})
            acc = validate_delta(d, [read_text])
            if isinstance(acc, str):
                self.drop_log.append(f"document {document_id}: {acc}")
                continue
            ev = Evidence(source="document", quote=acc.quote, turn_id=None, start_ms=None,
                          document_id=document_id, confidence_pct=acc.confidence_pct)
            policy.merge(self.state.fields, policy.new_field(acc.key, acc.value, ev))

    def _dispatch_advocate(self) -> None:
        ctx = egress.advocate_ctx(self.state.turns, policy.current_values(self.state.fields),
                                  self.state.result)
        advocate = self.providers.advocate
        self._dispatch("advocate", lambda: advocate.review(ctx))

    def _advocate_requests(self, out: AdvocateOut) -> list[ConfirmationRequest]:
        """Validated new confirmation requests (catalog key, typed value, quote in
        the turns, lexicon support, not already known)."""
        catalog = load_catalog()
        sources = [t.text for t in self.state.turns]
        known = {(c.key, c.value) for c in self.state.confirmations}
        n = len(self.state.confirmations)
        new: list[ConfirmationRequest] = []
        for item in out.requests:
            try:
                f = catalog.get(item.key)
            except KeyError:
                self.drop_log.append(f"advocate: unknown key {item.key!r}")
                continue
            d = DeltaOut(key=item.key, value_bool=item.value_bool, value_int=item.value_int,
                         value_enum=item.value_enum, value_text=item.value_text,
                         quote=item.quote, confidence_pct=0, answers_question_id=None)
            value = delta_value(d, f)
            if value is None or not quote_in(item.quote, sources):
                self.drop_log.append(f"advocate: invalid request for {item.key}")
                continue
            reason = supports(f, value, item.quote)
            if reason is not None:
                self.drop_log.append(f"advocate: {reason}")
                continue
            fs = self.state.fields.get(item.key)
            if (item.key, value) in known or (
                    fs is not None and fs.status == "confirmed" and fs.value == value):
                continue
            known.add((item.key, value))
            n += 1
            new.append(ConfirmationRequest(id=f"c{n}", key=item.key, value=value,
                                           quote=item.quote, rationale=item.rationale,
                                           status="pending"))
        return new

    def _apply_advocate(self, out: AdvocateOut) -> None:
        self.state.confirmations.extend(self._advocate_requests(out))

    # ------------------------------------------------------------ document

    def _on_document(self, image: bytes, mime: str, document_id: str) -> None:
        if self.state.phase == "finalized":
            self._error("finalized", "case is finalized")
            return
        if not self.state.muse_enabled:
            self._error("muse_disabled", "kill switch is on; documents are not read")
            return
        ctx = egress.vision_ctx(document_id)
        vision = self.providers.vision
        self._dispatch("vision", lambda: vision.read(image, mime, ctx), document_id=document_id)

    # ------------------------------------------------------------- client

    def _on_client(self, msg: dict[str, Any]) -> None:
        t = msg.get("type")
        if t == "text_turn":
            self._on_turn(str(msg.get("text", "")), msg.get("start_ms"), msg.get("end_ms"))
            return
        if t == "kill_switch":
            self._kill_switch(bool(msg.get("on")))
            return
        if t == "stop_audio":
            return  # handled by the WS layer (ASR stream)
        if self.state.phase == "finalized":
            self._error("finalized", f"{t}: case is finalized")
            return
        snap = self.state.snapshot
        try:
            if t == "confirm":
                policy.confirm(self.state.fields, str(msg["key"]))
                self.clinician.record("confirm", snap, key=str(msg["key"]))
            elif t == "reject":
                policy.reject(self.state.fields, str(msg["key"]))
                self.clinician.record("reject", snap, key=str(msg["key"]))
            elif t == "confirm_all":
                keys = policy.confirm_all(self.state.fields)
                self.clinician.record("confirm_all", snap, keys=",".join(keys))
            elif t == "edit":
                key = str(msg["key"])
                policy.edit(self.state.fields, key, msg.get("value"), self._now_ms())
                self.clinician.record("edit", snap, key=key, value=self.state.fields[key].value)
            elif t == "resolve_conflict":
                key, idx = str(msg["key"]), int(msg["choice_index"])
                policy.resolve_conflict(self.state.fields, key, idx)
                self.clinician.record("resolve_conflict", snap, key=key, choice_index=idx,
                                      value=self.state.fields[key].value)
            elif t == "skip_question":
                q = next((q for q in self.state.questions if q.id == msg.get("id")), None)
                if q is None or q.status != "pending":
                    raise policy.PolicyError("no such pending question")
                q.status = "skipped"
                self.clinician.record("skip_question", snap, id=q.id, key=q.key)
            elif t == "resolve_confirmation":
                self._resolve_confirmation(str(msg.get("id")), str(msg.get("decision")))
            elif t == "finalize":
                self._finalize()
                return
            else:
                raise policy.PolicyError(f"unknown message type {t!r}")
        except (policy.PolicyError, KeyError, ValueError, TypeError) as exc:
            self._error("bad_request", str(exc))
            return
        self._refresh()

    def _resolve_confirmation(self, cid: str, decision: str) -> None:
        req = next((c for c in self.state.confirmations if c.id == cid), None)
        if req is None or req.status != "pending":
            raise policy.PolicyError("no such pending confirmation")
        snap = self.state.snapshot
        if decision in ("confirm", "confirmed"):
            req.status = "confirmed"
            ev = Evidence(source="advocate", quote=req.quote, turn_id=None, start_ms=None,
                          document_id=None, confidence_pct=100)
            old = self.state.fields.get(req.key)
            self.state.fields[req.key] = FieldState(
                key=req.key, value=req.value, status="confirmed",
                evidence=[*(old.evidence if old else []), ev], sticky_alert=False,
                conflict=None)
        elif decision in ("dismiss", "dismissed"):
            req.status = "dismissed"
        else:
            raise policy.PolicyError(f"bad decision {decision!r}")
        self.clinician.record("resolve_confirmation", snap, id=cid, key=req.key,
                              decision=req.status)

    def _kill_switch(self, on: bool) -> None:
        """L4: epoch += 1, in-flight results discarded, no new model calls.
        State (C, P, pending confirmations) is kept and keeps counting."""
        self.state.epoch += 1
        self.state.muse_enabled = not on
        self.clinician.record("kill_switch", self.state.snapshot, on=on)
        self._extracting = 0
        self._refresh(bump=self.state.phase == "live")

    # ------------------------------------------------------------ finalize

    def _finalize(self) -> None:
        blockers = policy.finalize_blockers(self.state.fields, self.state.confirmations)
        if blockers:
            self._error("finalize_blocked", "; ".join(blockers))
            return
        self.clinician.record("finalize", self.state.snapshot)
        self.state.epoch += 1
        self.state.snapshot += 1
        self.state.phase = "finalized"
        self._refresh(bump=False)  # last evaluation on the frozen state; no planning
        for q in self.state.questions:
            if q.status == "pending":
                q.status = "skipped"
        assert self.state.result is not None and self._eval is not None
        snap = self.state.snapshot
        self.state.letter = build_letter(self.state.fields, self.state.result, snap)
        self.state.receipt = build_receipt(
            session_id=self.state.session_id, snapshot=snap, turns=self.state.turns,
            confirmed=policy.confirmed_values(self.state.fields), result=self.state.result,
            clinician_actions=self.clinician.actions, model_ids=self.providers.model_ids,
            prompt_hashes=prompt_hashes(),
            created_at=self.clock().isoformat(timespec="seconds"))
        if not self.state.muse_enabled:
            self.state.reasoning = _unavailable("muse disabled (kill switch)")
            self._broadcast(self._state_msg())
            return
        self._broadcast(self._state_msg())
        self._final_task = asyncio.create_task(self._final_pass(self.state.epoch))

    async def _final_pass(self, epoch: int) -> None:
        """Reasoner + advocate (last pass) in parallel, 12 s timeout each."""
        assert self._eval is not None and self.state.result is not None
        result = self.state.result
        chunks = get_grounding().retrieve(self._eval.r_cp.differential,
                                          policy.project(policy.all_values(self.state.fields)))
        grounding = [GroundingChunkView(chunk_id=c.source_id, text=c.text) for c in chunks]
        reasoner = (self.providers.reasoner_wonder if result.red_flags
                    else self.providers.reasoner_spark)
        rctx = egress.reasoner_ctx(policy.confirmed_values(self.state.fields), result, grounding)
        actx = egress.advocate_ctx(self.state.turns, policy.current_values(self.state.fields),
                                   result)
        r_out, a_out = await asyncio.gather(
            asyncio.wait_for(reasoner.explain(rctx), self.timeout),
            asyncio.wait_for(self.providers.advocate.review(actx), self.timeout),
            return_exceptions=True)
        meta = {"model_id": reasoner.model_id, "delivered": [g.chunk_id for g in grounding]}
        await self._q.put(("final", _Job(epoch, "final", _noop, meta), r_out, a_out))

    def _on_final(self, job: _Job, r_out: Any, a_out: Any) -> None:
        if job.epoch != self.state.epoch:
            self.discarded.append(f"final@epoch{job.epoch}")
            return
        if isinstance(r_out, ReasonerOut):
            delivered = set(job.meta["delivered"])
            cited = [c for c in r_out.cited_chunk_ids if c in delivered]
            # L3: r_out.suggested_urgency is NEVER applied to the decision.
            view = ReasonerView(model_used=job.meta["model_id"], explanation=r_out.explanation,
                                reconciliation=r_out.reconciliation,
                                suggested_next_steps=list(r_out.suggested_next_steps),
                                cited_chunk_ids=cited,
                                citations_verified=len(cited) == len(r_out.cited_chunk_ids))
        else:
            view = _unavailable(type(r_out).__name__)
        if isinstance(a_out, AdvocateOut):
            catalog = load_catalog()
            for req in self._advocate_requests(a_out):
                label = catalog.get(req.key).label_es
                view.suggested_next_steps.append(
                    f"Revisar (advocate): {label} — «{req.quote}»")
        self.state.reasoning = view
        self._broadcast(self._state_msg())

    # ------------------------------------------------------------- refresh

    def _refresh(self, bump: bool = True) -> None:
        """Re-evaluate, close answered questions, plan, update the clock, push."""
        st = self.state
        self._eval = policy.evaluate_state(st.fields, st.confirmations)
        st.result = self._eval.view
        for q in st.questions:
            if q.status == "pending" and q.key in st.fields:
                q.status = "answered"
        if st.phase == "live" and self._extracting == 0:
            p = plan(st.fields, st.questions, bool(st.result.red_flags))
            if p is not None:
                q = to_question(p, f"q{len(st.questions) + 1}")
                st.questions.append(q)
                draft = egress.phrase_draft(p.draft.model_copy(update={"id": q.id}))
                phraser = self.providers.phraser
                self._dispatch("phrase", lambda: phraser.phrase(draft), question_id=q.id)
        st.onset = compute_onset(st.fields, st.turns, st.result, st.confirmations,
                                 self._t0, self.clock())
        if bump and st.phase == "live":
            st.snapshot += 1
        self._broadcast(self._state_msg())

    # ------------------------------------------------------- public helpers

    async def document(self, image: bytes, mime: str, document_id: str) -> None:
        await self.submit("document", image, mime, document_id)


async def _noop() -> None:
    return None


def _unavailable(why: str) -> ReasonerView:
    return ReasonerView(model_used="unavailable", explanation="unavailable",
                        reconciliation=why, suggested_next_steps=[], cited_chunk_ids=[],
                        citations_verified=False)


__all__ = ["MODEL_TIMEOUT_S", "Session", "prompt_hashes", "utcnow"]

"""End-to-end demo cases A and B via `text_turn` (SPECS §8) + finalize flow."""
from __future__ import annotations

import asyncio

from api.demo_cases import BUILTIN_DEMO_CASES
from api.listen.contracts import ReasonerOut
from api.listen.testkit import FixedClock, dictate, new_session, send
from api.muse.interfaces import ReasonerCtx

CASE = {c["id"]: c for c in BUILTIN_DEMO_CASES}
A_TURNS = [t["text"] for t in CASE["A"]["turns"]]
B_TURNS = [t["text"] for t in CASE["B"]["turns"]]


async def test_case_a_end_to_end() -> None:
    s = new_session()
    await dictate(s, A_TURNS)
    pending = [q for q in s.state.questions if q.status == "pending"]
    assert [q.key for q in pending] == ["dix_hallpike"]
    q = pending[0]
    assert q.impact > 0 and "Ambulatoria" in q.reason and "Epley" in q.reason
    await dictate(s, [CASE["A"]["answers"]["dix_hallpike"]])
    assert q.status == "answered"
    assert s.state.fields["dix_hallpike"].value == "right_positive"
    assert s.state.fields["dix_hallpike"].evidence[0].source == "answered"
    # unconfirmed → conservative (L1)
    assert s.state.result is not None and s.state.result.urgency == "prioritaria"
    await send(s, {"type": "confirm_all"})
    r = s.state.result
    assert r.urgency == "ambulatoria" and "EPLEY" not in r.blocked_actions
    assert r.red_flags == [] and r.differential[0].diagnosis == "bppv_posterior"
    assert r.referral_label_es == "Manejo ambulatorio / control en APS"
    gold = CASE["A"]["gold"]["fields"]
    assert {k: fs.value for k, fs in s.state.fields.items()} == gold
    assert s.state.onset is None  # no red flag, no pending confirmation
    await send(s, {"type": "finalize"})
    assert s.state.phase == "finalized" and s.state.receipt is not None
    assert s.state.reasoning is not None and s.state.reasoning.model_used == "mock-reasoner"


async def test_case_b_end_to_end() -> None:
    s = new_session(clock=FixedClock(step_ms=1000))
    await dictate(s, B_TURNS)
    r = s.state.result
    assert r is not None and r.urgency == "inmediata"
    assert "EPLEY" in r.blocked_actions and "DERIVAR_URGENTE" in r.forced_actions
    assert {h.id for h in r.red_flags} == {"A5", "A7"}
    assert all(h.provisional for h in r.red_flags)
    dip = s.state.fields["focal_signs.diplopia"]
    assert dip.value is True and dip.sticky_alert and dip.status == "proposed"
    assert dip.evidence[0].quote == "Ayer vio doble un rato"
    gold = CASE["B"]["gold"]["fields"]
    assert {k: fs.value for k, fs in s.state.fields.items()} == gold
    # window clock: red flag shown + onset time
    assert s.state.onset is not None
    assert [w.minutes for w in s.state.onset.windows] == [270, 1440]
    assert s.state.onset.windows[0].remaining_min == 0
    # finalize blocked while the sticky alert is unconfirmed
    await send(s, {"type": "finalize"})
    assert s.state.phase == "live"
    assert any("sticky_alert:focal_signs.diplopia" in e for e in s.state.errors)
    await send(s, {"type": "confirm", "key": "focal_signs.diplopia"})
    await send(s, {"type": "confirm_all"})
    r = s.state.result
    assert r.urgency == "inmediata" and r.source_eval == "confirmed"
    assert not any(h.provisional for h in r.red_flags)
    await send(s, {"type": "finalize"})
    assert s.state.phase == "finalized"
    assert s.state.letter is not None and s.state.receipt is not None
    assert s.state.letter.generated_from_snapshot == s.state.receipt.snapshot
    assert s.state.reasoning is not None and "A5" in s.state.reasoning.explanation
    # after finalize: clinician edits and dictation are refused
    snap = s.state.snapshot
    await send(s, {"type": "edit", "key": "age_years", "value": 30})
    await dictate(s, ["sin diplopía"])
    assert s.state.fields["age_years"].value == 68 and s.state.snapshot == snap


async def test_kill_switch_demo_order() -> None:
    """SPECS §8.3: B's red flag confirmed → kill switch → urgency, blocks and clock unchanged."""
    s = new_session()
    await dictate(s, B_TURNS)
    await send(s, {"type": "confirm", "key": "focal_signs.diplopia"})
    before = (s.state.result, s.state.onset)
    await send(s, {"type": "kill_switch", "on": True})
    assert (s.state.result, s.state.onset) == before
    await send(s, {"type": "confirm_all"})
    await send(s, {"type": "finalize"})
    assert s.state.phase == "finalized"
    assert s.state.reasoning is not None and s.state.reasoning.model_used == "unavailable"


async def test_document_proposes_fact() -> None:
    s = new_session()
    await dictate(s, B_TURNS)
    await s.document("Paciente anticoagulado con acenocumarol.".encode(), "image/png", "B-meds")
    await s.drain()
    fs = s.state.fields["context.anticoagulated"]
    assert fs.value is True and fs.status == "proposed"
    assert fs.evidence[0].source == "document" and fs.evidence[0].document_id == "B-meds"


async def test_short_answers() -> None:
    s = new_session()
    await dictate(s, A_TURNS)
    q = next(q for q in s.state.questions if q.status == "pending")
    await dictate(s, ["No lo evalué."])
    assert q.status == "skipped" and "dix_hallpike" not in s.state.fields
    q2 = next(q for q in s.state.questions if q.status == "pending")
    assert q2.key != "dix_hallpike"
    await dictate(s, ["No."])
    assert q2.status == "answered"
    assert s.state.fields[q2.key].evidence[0].source == "answered"


async def test_finalize_reasoner_timeout_shows_unavailable() -> None:
    class Hung:
        model_id = "hung"

        async def explain(self, ctx: ReasonerCtx) -> ReasonerOut:
            await asyncio.sleep(10)
            raise AssertionError

    s = new_session(reasoner_spark=Hung(), reasoner_wonder=Hung())
    s.timeout = 0.05
    await dictate(s, A_TURNS)
    await send(s, {"type": "confirm_all"})
    await send(s, {"type": "finalize"})
    assert s.state.reasoning is not None
    assert s.state.reasoning.explanation == "unavailable"
    assert s.state.receipt is not None


async def test_at_most_one_pending_question() -> None:
    s = new_session()
    for t in [*A_TURNS, "No.", "No.", "No.", "No.", "No.", "No.", "No."]:
        await dictate(s, [t])
        assert sum(q.status == "pending" for q in s.state.questions) <= 1
    assert len(s.state.questions) <= 6

"""English dictation: the evidence gate (L2) holds in English exactly as in Spanish,
and the English demo cases A-en / B-en land on the same decisions as A / B."""
from __future__ import annotations

import pytest

from api.catalog import load_catalog
from api.demo_cases import BUILTIN_DEMO_CASES, ENGLISH_DEMO_CASES, all_demo_cases, load_demo_cases
from api.listen import registry
from api.listen.contracts import DeltaOut
from api.listen.evidence import classify_short_answer, int_supported, supports, validate_delta
from api.listen.numbers import minutes_ago, numbers_in
from api.listen.testkit import FixedClock, dictate, new_session, send
from api.muse.client import prompt_name_for

EN = {c["id"]: c for c in ENGLISH_DEMO_CASES}
ES = {c["id"]: c for c in BUILTIN_DEMO_CASES}
CAT = load_catalog()


def _bool(key: str, value: bool, quote: str) -> str | None:
    return supports(CAT.get(key), value, quote, CAT)


# ------------------------------------------------------------- E-neg in English


@pytest.mark.parametrize("quote", [
    "no diplopia",
    "No hearing loss or tinnitus, no diplopia",
    "without double vision",
    "denies diplopia",
    "negative for diplopia",
    "diplopia absent",
])
def test_negated_english_term_never_supports_true(quote: str) -> None:
    key = "tinnitus" if quote.startswith("No hearing") else "focal_signs.diplopia"
    reason = _bool(key, True, quote)
    assert reason is not None and reason.startswith("E-neg")
    assert _bool(key, False, quote) is None


@pytest.mark.parametrize("quote", [
    "Yesterday the patient saw double for a while",
    "slurred speech noticed by the family",
    "no headache but with double vision",  # "but"/"with" end the negation's scope
])
def test_affirmed_english_term_supports_true(quote: str) -> None:
    key = "focal_signs.dysarthria" if "slurred" in quote else "focal_signs.diplopia"
    assert _bool(key, True, quote) is None


def test_english_enum_needs_its_own_term() -> None:
    f = CAT.get("dix_hallpike")
    assert supports(f, "right_positive", "Right positive, torsional", CAT) is None
    assert supports(f, "left_positive", "Right positive, torsional", CAT) is not None


def test_english_quote_must_be_in_the_source() -> None:
    d = DeltaOut(key="focal_signs.diplopia", value_bool=True, value_int=None, value_enum=None,
                 value_text=None, quote="saw double", confidence_pct=80,
                 answers_question_id=None)
    assert not isinstance(validate_delta(d, ["Yesterday the patient saw double."]), str)
    assert validate_delta(d, ["No visual symptoms."]) == \
        "E-quote: quote for focal_signs.diplopia not found in source"


# ---------------------------------------------------------- numbers and answers


@pytest.mark.parametrize(("text", "value"), [
    ("68-year-old patient", 68),
    ("sixty-eight years old", 68),
    ("one hundred and twenty", 120),
    ("twelve", 12),
    ("sesenta y ocho años", 68),  # Spanish unchanged
])
def test_english_and_spanish_numbers(text: str, value: int) -> None:
    from api.listen.evidence import tokens

    assert numbers_in(tokens(text))[0][0] == value


@pytest.mark.parametrize(("text", "minutes"), [
    ("constant vertigo that started 12 hours ago", 720),
    ("twelve hours ago", 720),
    ("two days ago", 2880),
    ("hace 12 horas", 720),
    ("an hour ago", None),  # no number stated
])
def test_minutes_ago(text: str, minutes: int | None) -> None:
    from api.listen.evidence import tokens

    assert minutes_ago(tokens(text)) == minutes


def test_last_known_well_value_must_match_english_quote() -> None:
    key = "context.last_known_well_minutes_ago"
    assert int_supported(key, 720, "started 12 hours ago") is None
    assert int_supported(key, 700, "started 12 hours ago") is not None
    assert int_supported("age_years", 68, "68-year-old patient") is None
    assert int_supported("age_years", 86, "68-year-old patient") is not None


@pytest.mark.parametrize(("text", "kind"), [
    ("Yes.", "yes"), ("Positive", "yes"), ("No, no diplopia.", "no"), ("Negative", "no"),
    ("Not assessed.", "skip"), ("I didn't check", "skip"),
    ("No diplopia reported", None), ("Right positive, torsional", None),
])
def test_english_short_answers(text: str, kind: str | None) -> None:
    assert classify_short_answer(text) == kind


# ------------------------------------------------------------- session language


def test_session_language() -> None:
    assert registry.session_lang(None, None) == "es"
    assert registry.session_lang("en", None) == "en"
    assert registry.session_lang("es", "A-en") == "en"  # the case's language wins
    assert registry.session_lang("en", "A") == "es"
    with pytest.raises(ValueError):
        registry.session_lang("fr", None)


def test_english_prompts_only_for_localized_roles() -> None:
    assert prompt_name_for("extractor", "en") == "extractor_en"
    assert prompt_name_for("extractor", "es") == "extractor"
    assert prompt_name_for("phrasing", "en") == "phrasing"  # already bilingual
    assert prompt_name_for("vision", "en") == "vision"


def test_english_cases_are_demo_only() -> None:
    ids = [c["id"] for c in all_demo_cases()]
    assert ids[-2:] == ["A-en", "B-en"]
    assert not {"A-en", "B-en"} & {c["id"] for c in load_demo_cases()}  # bench stays Spanish
    for cid in ("A", "B"):
        assert EN[f"{cid}-en"]["gold"] == ES[cid]["gold"]


# ------------------------------------------------- end to end (mock providers)


async def test_case_a_en_end_to_end() -> None:
    s = new_session()
    await dictate(s, [t["text"] for t in EN["A-en"]["turns"]])
    pending = [q for q in s.state.questions if q.status == "pending"]
    assert [q.key for q in pending] == ["dix_hallpike"]
    await dictate(s, [EN["A-en"]["answers"]["dix_hallpike"]])
    assert s.state.fields["dix_hallpike"].value == "right_positive"
    assert s.state.result is not None and s.state.result.urgency == "prioritaria"  # L1
    await send(s, {"type": "confirm_all"})
    r = s.state.result
    assert r.urgency == "ambulatoria" and "EPLEY" not in r.blocked_actions
    assert {k: fs.value for k, fs in s.state.fields.items()} == EN["A-en"]["gold"]["fields"]


async def test_case_b_en_end_to_end() -> None:
    s = new_session(clock=FixedClock(step_ms=1000))
    await dictate(s, [t["text"] for t in EN["B-en"]["turns"]])
    r = s.state.result
    assert r is not None and r.urgency == "inmediata"
    assert "EPLEY" in r.blocked_actions and {h.id for h in r.red_flags} == {"A5", "A7"}
    dip = s.state.fields["focal_signs.diplopia"]
    assert dip.value is True and dip.sticky_alert and dip.status == "proposed"
    assert dip.evidence[0].quote == "Yesterday the patient saw double for a while"
    assert {k: fs.value for k, fs in s.state.fields.items()} == EN["B-en"]["gold"]["fields"]
    assert s.state.onset is not None


async def test_english_negations_never_raise_alerts() -> None:
    s = new_session()
    await dictate(s, ["70-year-old patient, no diplopia, without slurred speech, "
                      "denies trouble swallowing."])
    for key in ("focal_signs.diplopia", "focal_signs.dysarthria", "focal_signs.dysphagia"):
        fs = s.state.fields.get(key)
        assert fs is None or (fs.value is False and not fs.sticky_alert)


# --------------------------------------- replay: recorded Meta answers, offline


def _replay_session(case_id: str):  # type: ignore[no-untyped-def]
    lang = registry.session_lang(None, case_id)
    return registry.Session(case_id, registry.build("replay", case_id, lang),
                            clock=FixedClock(), lang=lang)


async def test_case_a_en_replay_session() -> None:
    s = _replay_session("A-en")
    await dictate(s, [t["text"] for t in EN["A-en"]["turns"]])
    assert [q.key for q in s.state.questions if q.status == "pending"] == ["dix_hallpike"]
    await dictate(s, [EN["A-en"]["answers"]["dix_hallpike"]])
    assert s.state.errors == []
    assert s.state.result is not None and s.state.result.urgency == "prioritaria"  # L1
    await send(s, {"type": "confirm_all"})
    assert s.state.result.urgency == "ambulatoria"
    assert "EPLEY" not in s.state.result.blocked_actions
    await send(s, {"type": "finalize"})
    assert s.state.phase == "finalized"
    assert s.state.reasoning is not None and s.state.reasoning.explanation  # English prompt


async def test_case_b_en_replay_session() -> None:
    s = _replay_session("B-en")
    await dictate(s, [t["text"] for t in EN["B-en"]["turns"]])
    st = s.state
    assert st.errors == [] and st.result is not None
    assert st.result.urgency == "inmediata" and "EPLEY" in st.result.blocked_actions
    dip = st.fields["focal_signs.diplopia"]
    assert dip.value is True and dip.sticky_alert
    assert "saw double" in dip.evidence[0].quote
    assert [(c.key, c.status) for c in st.confirmations] == [("focal_signs.diplopia", "pending")]
    await send(s, {"type": "confirm", "key": "focal_signs.diplopia"})
    await send(s, {"type": "confirm_all"})
    await send(s, {"type": "finalize"})
    assert s.state.phase == "finalized" and s.state.receipt is not None
    assert s.state.result is not None and s.state.result.urgency == "inmediata"
    assert s.state.reasoning is not None and s.state.reasoning.explanation


async def test_english_letter_names_the_urgency() -> None:
    s = new_session()
    await dictate(s, [t["text"] for t in EN["A-en"]["turns"]])
    await dictate(s, [EN["A-en"]["answers"]["dix_hallpike"]])
    await send(s, {"type": "confirm_all"})
    await send(s, {"type": "finalize"})
    assert s.state.letter is not None
    lines = [st.text_en for sec in s.state.letter.sections for st in sec.statements]
    assert "Urgency: Outpatient." in lines

"""Deterministic, rule-based fake providers (SPECS §5.3) — no network.

- `MockExtractor`: maps catalog-lexicon hits in a turn to `DeltaOut`s. Quotes
  are verbatim clauses of the turn (so E-quote holds); a term preceded by a
  negation cue within the catalog's token window, inside the same clause,
  yields `false` (E-neg), never `true`.
- `MockAsrStream`: emits speech_start / cumulative partials / final /
  speech_end from a text script with word-rate timing (`speed=0` → instant).
- `MockAsrFile`, `MockPhraser`, `MockAdvocate`, `MockVision`, `MockReasoner`:
  template/lexicon fakes with the same contracts as the live providers.

Everything is a pure function of its input: same input → same output.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass

from api.catalog import Catalog, CatalogField, load_catalog, normalize
from api.demo_cases import BUILTIN_DEMO_CASES
from api.listen.contracts import (
    AdvocateItemOut,
    AdvocateOut,
    DeltaOut,
    ExtractorOut,
    PhrasingOut,
    ReasonerOut,
    Turn,
    VisionOut,
)
from api.muse.interfaces import (
    AdvocateCtx,
    AsrEvent,
    ExtractCtx,
    Providers,
    QuestionDraft,
    ReasonerCtx,
    VisionCtx,
)

MOCK_CONFIDENCE_PCT = 90

_NUMBER_WORDS: dict[str, int] = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "veinte": 20,
    "treinta": 30,
}
_POSTFIX_NEGATIONS = {"negativo", "negativa", "ausente"}
_NEGATION_BREAKERS = {"con", "pero"}
_CLAUSE_SPLIT = re.compile(r"[.;:,¿?¡!\n]+")
_TOKEN = re.compile(r"[a-z0-9]+")

# Keys whose positive value is a central/safety alert: the mock advocate raises
# a confirmation request when the dictation mentions one the form lacks.
ADVOCATE_ALERT_KEYS: tuple[str, ...] = (
    "focal_signs.diplopia",
    "focal_signs.dysarthria",
    "focal_signs.dysphagia",
    "focal_signs.limb_weakness",
    "focal_signs.facial_droop",
    "focal_signs.numbness",
    "focal_signs.hiccups",
    "focal_signs.horner",
    "truncal_ataxia_severe",
    "headache_neck_pain_sudden_severe",
    "altered_consciousness",
    "skew_deviation",
    "nystagmus_direction_changing_gaze",
    "presyncope_syncope",
    "context.anticoagulated",
)


# ------------------------------------------------------------------ matching


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))


def _clauses(text: str) -> list[str]:
    """Original-case clauses (verbatim substrings of `text`)."""
    return [c.strip() for c in _CLAUSE_SPLIT.split(text) if c.strip()]


def _find(tokens: list[str], term: list[str]) -> list[int]:
    n = len(term)
    return [i for i in range(len(tokens) - n + 1) if tokens[i : i + n] == term]


def _negated(tokens: list[str], start: int, end: int, cues: list[list[str]], window: int) -> bool:
    lo = start
    for back in range(1, window + 1):
        i = start - back
        if i < 0 or tokens[i] in _NEGATION_BREAKERS:
            break
        lo = i
    before = tokens[lo:start]
    if any(_find(before, cue) for cue in cues):
        return True
    after = tokens[end : end + 2]
    return any(t in _POSTFIX_NEGATIONS for t in after)


def _number_near(tokens: list[str], start: int, end: int) -> int | None:
    """An integer stated right before the term (`68 años`, `tres episodios`)."""
    for i in (start - 1, start - 2):
        if i < 0:
            continue
        t = tokens[i]
        if i > 0 and tokens[i - 1] == "hace":
            return None  # "hace 3 años" is a time, not an age
        if t.isdigit():
            return int(t)
        if t in _NUMBER_WORDS:
            return _NUMBER_WORDS[t]
    return None


_DECIMAL = re.compile(r"(\d+(?:[.,]\d+)?)")
_LKW = re.compile(
    r"\bhace\s+(\d+|" + "|".join(_NUMBER_WORDS) + r")\s*(horas?|h|minutos?|min|dias?)\b"
)
_MEDS = re.compile(r"\b(?:toma|usa|en tratamiento con)\s+(.+)$", re.IGNORECASE)


def _delta(key: str, quote: str, *, b: bool | None = None, i: int | None = None,
           e: str | None = None, t: str | None = None, qid: str | None = None) -> DeltaOut:
    return DeltaOut(key=key, value_bool=b, value_int=i, value_enum=e, value_text=t, quote=quote,
                    confidence_pct=MOCK_CONFIDENCE_PCT, answers_question_id=qid)


def _match_field(field: CatalogField, clause: str, tokens: list[str], catalog: Catalog,
                 cues: list[list[str]]) -> DeltaOut | None:
    norm = normalize(clause)
    if field.type == "enum":
        best: tuple[int, str] | None = None
        for value, terms in field.lexicon.items():
            for term in terms:
                tt = _tokens(term)
                if tt and _find(tokens, tt) and (best is None or len(tt) > best[0]):
                    best = (len(tt), value)
        return _delta(field.key, clause, e=best[1]) if best else None

    if field.key == "context.last_known_well_minutes_ago":
        m = _LKW.search(norm)
        if not m:
            return None
        n = int(m.group(1)) if m.group(1).isdigit() else _NUMBER_WORDS[m.group(1)]
        unit = m.group(2)
        factor = 60 if unit.startswith("h") else 1440 if unit.startswith("d") else 1
        return _delta(field.key, clause, i=n * factor)

    if field.type == "str":
        m = _MEDS.search(clause)
        return _delta(field.key, clause, t=m.group(1).strip()) if m else None

    hits: list[tuple[int, int, str, str]] = []  # (start, end, lexicon bucket, term)
    for bucket, terms in field.lexicon.items():
        for term in terms:
            tt = _tokens(term)
            hits += [(s, s + len(tt), bucket, term) for s in _find(tokens, tt)] if tt else []
    if not hits:
        return None
    hits.sort()

    if field.type == "bool":
        if any(bucket == "false" for _, _, bucket, _ in hits):
            return _delta(field.key, clause, b=False)
        s, e, _, _ = hits[0]
        return _delta(field.key, clause,
                      b=not _negated(tokens, s, e, cues, catalog.negation_window_tokens))
    if field.type == "int":
        for s, e, _, _ in hits:
            num = _number_near(tokens, s, e)
            if num is not None:
                return _delta(field.key, clause, i=num)
        return None
    if field.type == "float":
        pos = max(0, norm.find(normalize(hits[0][3])))
        m = _DECIMAL.search(norm, pos)
        if not m:
            return None
        return _delta(field.key, clause, t=f"{float(m.group(1).replace(',', '.')):.1f}")
    return None


def extract_text(text: str, keys: Iterable[str] | None = None,
                 question_key: str | None = None, question_id: str | None = None,
                 catalog: Catalog | None = None) -> list[DeltaOut]:
    """Lexicon extraction over `text`. Later clauses supersede earlier ones per key."""
    catalog = catalog or load_catalog()
    allowed = set(keys) if keys is not None else set(catalog.keys)
    cues = [_tokens(c) for c in catalog.negation_cues]
    out: dict[str, DeltaOut] = {}
    for clause in _clauses(text):
        tokens = _tokens(clause)
        for field in catalog.fields:
            if field.key not in allowed:
                continue
            d = _match_field(field, clause, tokens, catalog, cues)
            if d is not None:
                if question_key is not None and d.key == question_key:
                    d = d.model_copy(update={"answers_question_id": question_id})
                out.pop(d.key, None)
                out[d.key] = d
    return list(out.values())


# ----------------------------------------------------------------- providers


class MockExtractor:
    async def extract(self, ctx: ExtractCtx) -> ExtractorOut:
        q = ctx.pending_question
        return ExtractorOut(deltas=extract_text(
            ctx.new_turn.text, ctx.catalog_keys,
            question_key=q.key if q else None, question_id=q.id if q else None))


class MockPhraser:
    async def phrase(self, q: QuestionDraft) -> PhrasingOut:
        if q.enum_values:
            labels = q.enum_labels_es or {}
            opts = ", ".join(labels.get(v, v).lower() for v in q.enum_values)
            return PhrasingOut(text_es=f"¿{q.label_es}? ({opts})",
                               text_en=f"{q.label_en}? ({', '.join(q.enum_values)})")
        return PhrasingOut(text_es=f"¿{q.label_es}: presente o ausente?",
                           text_en=f"{q.label_en}: present or absent?")


class MockAdvocate:
    async def review(self, ctx: AdvocateCtx) -> AdvocateOut:
        keys = [k for k in ADVOCATE_ALERT_KEYS if k in ctx.catalog_keys]
        requests: dict[str, AdvocateItemOut] = {}
        for turn in ctx.turns:
            for d in extract_text(turn.text, keys):
                if d.value_bool is True and d.key not in ctx.current_values:
                    requests[d.key] = AdvocateItemOut(
                        key=d.key, value_bool=True, value_int=None, value_enum=None,
                        value_text=None, quote=d.quote,
                        rationale="Mencionado en el dictado y ausente del formulario.")
        return AdvocateOut(requests=list(requests.values()))


class MockVision:
    """Treats a UTF-8 decodable 'image' as the document's text (test fixtures)."""

    async def read(self, image: bytes, mime: str, ctx: VisionCtx) -> VisionOut:
        try:
            text = image.decode("utf-8")
        except UnicodeDecodeError:
            return VisionOut(deltas=[], read_text="")
        return VisionOut(deltas=extract_text(text, ctx.catalog_keys), read_text=text)


@dataclass
class MockReasoner:
    model_id: str = "mock-reasoner"

    async def explain(self, ctx: ReasonerCtx) -> ReasonerOut:
        r = ctx.result
        flags = ", ".join(f"{h.id} ({h.label})" for h in r.red_flags) or "ninguna"
        top = r.differential[0].diagnosis if r.differential else "indeterminado"
        return ReasonerOut(
            explanation=f"Banderas rojas: {flags}. Hipótesis principal (apoyo): {top}.",
            reconciliation="La urgencia proviene del motor determinístico.",
            suggested_next_steps=[],
            suggested_urgency=None,
            cited_chunk_ids=[c.chunk_id for c in ctx.grounding[:2]],
        )


# ----------------------------------------------------------------------- ASR


@dataclass(frozen=True)
class ScriptTurn:
    text: str
    start_ms: int
    end_ms: int


def script_from_text(text: str, wpm: int = 150, gap_ms: int = 700) -> list[ScriptTurn]:
    """One turn per non-empty line; duration from words-per-minute."""
    out: list[ScriptTurn] = []
    t = 0
    for line in (ln.strip() for ln in text.splitlines()):
        if not line:
            continue
        dur = max(400, round(len(line.split()) * 60_000 / wpm))
        out.append(ScriptTurn(line, t, t + dur))
        t += dur + gap_ms
    return out


class MockAsrStream:
    """Ignores audio; replays a scripted dictation as Meta-shaped ASR events."""

    def __init__(self, script: list[ScriptTurn], speed: float = 0.0, words_per_partial: int = 3,
                 first_turn_id: int = 1) -> None:
        self._script = script
        self._speed = speed
        self._step = words_per_partial
        self._first = first_turn_id
        self._closed = False
        self.bytes_fed = 0

    async def feed(self, pcm: bytes) -> None:
        self.bytes_fed += len(pcm)

    async def close(self) -> None:
        self._closed = True

    async def _wait(self, ms: int) -> None:
        await asyncio.sleep(ms * self._speed / 1000 if self._speed > 0 else 0)

    async def events(self) -> AsyncIterator[AsrEvent]:
        clock = 0
        for n, st in enumerate(self._script):
            if self._closed:
                return
            tid = self._first + n
            await self._wait(st.start_ms - clock)
            yield AsrEvent(kind="speech_start", turn_id=tid, start_ms=st.start_ms)
            words = st.text.split()
            span = st.end_ms - st.start_ms
            for k in range(self._step, len(words), self._step):
                await self._wait(span * self._step // max(1, len(words)))
                if self._closed:
                    return
                yield AsrEvent(kind="partial", turn_id=tid, text=" ".join(words[:k]),
                               start_ms=st.start_ms)
            yield AsrEvent(kind="final", turn_id=tid, text=st.text, start_ms=st.start_ms,
                           end_ms=st.end_ms)
            yield AsrEvent(kind="speech_end", turn_id=tid, end_ms=st.end_ms)
            clock = st.end_ms


class MockAsrFile:
    def __init__(self, script: list[ScriptTurn]) -> None:
        self._script = script

    async def transcribe(self, wav: bytes, first_turn_id: int) -> list[Turn]:
        return [Turn(turn_id=first_turn_id + n, start_ms=s.start_ms, end_ms=s.end_ms, text=s.text)
                for n, s in enumerate(self._script)]


def _default_script() -> list[ScriptTurn]:
    case_b = next(c for c in BUILTIN_DEMO_CASES if c["id"] == "B")
    return [ScriptTurn(t["text"], t["start_ms"], t["end_ms"]) for t in case_b["turns"]]


MOCK_MODEL_IDS: dict[str, str] = {
    "asr": "mock-asr", "extractor": "mock-extractor", "phraser": "mock-phraser",
    "advocate": "mock-advocate", "vision": "mock-vision", "reasoner_spark": "mock-reasoner",
    "reasoner_wonder": "mock-reasoner",
}


def build_providers(script: list[ScriptTurn] | None = None, speed: float = 0.0) -> Providers:
    s = script if script is not None else _default_script()
    return Providers(
        mode="mock",
        open_asr=lambda: MockAsrStream(s, speed=speed),
        asr_file=MockAsrFile(s),
        extractor=MockExtractor(),
        phraser=MockPhraser(),
        advocate=MockAdvocate(),
        vision=MockVision(),
        reasoner_spark=MockReasoner("mock-reasoner"),
        reasoner_wonder=MockReasoner("mock-reasoner"),
        model_ids=dict(MOCK_MODEL_IDS),
    )

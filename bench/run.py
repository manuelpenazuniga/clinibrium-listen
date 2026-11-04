"""Bench runner: keyword baseline vs the Muse extractor on scripted dictations.

For each case, both systems read the dictation turn by turn (then the scripted
answers, each with its question pending), the extracted atomic fields are
projected to `CaseFeatures` and evaluated with the frozen engine, and the result
is compared with the gold labels.

    uv run python bench/run.py --mode mock      # deterministic fakes, offline
    uv run python bench/run.py --mode replay    # recorded fixtures, offline
    MUSE_MAX_LIVE_CALLS=40 uv run python bench/run.py --mode live

Network policy: `mock` and `replay` run with outbound sockets disabled (any
connection attempt raises). `live` prints the planned number of extractor calls
and refuses to start unless `MUSE_MAX_LIVE_CALLS` is set and the plan fits.

Outputs: bench/results/<mode>.json (full detail), bench/results/table.md and
bench/results/table.json (summary for the README and the web /bench page).
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import socket
import statistics
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT / "engine"), str(_ROOT)]  # as in scripts/gen_catalog.py

from adapter import engine_version  # noqa: E402
from api.catalog import load_catalog, normalize  # noqa: E402
from api.listen.contracts import DeltaOut, Evidence, FieldState, Question, Turn  # noqa: E402
from api.listen.planner import plan, procedure_keys, to_question  # noqa: E402
from api.listen.policy import new_field  # noqa: E402
from api.muse.interfaces import ExtractCtx, Extractor, MuseMode, get_providers  # noqa: E402
from bench import baseline  # noqa: E402
from bench.common import (  # noqa: E402
    RESULTS_DIR,
    Fields,
    FieldValue,
    Urgency,
    check_value,
    evaluate_fields,
    is_negative_gold,
    load_cases,
    top1,
    under_triage,
    values_equal,
)

SYSTEMS = ("baseline", "muse")
CHARS_PER_TOKEN = 4  # rough token estimate for the cost column

# ---------------------------------------------------------------- policy bits


ShortAnswer = Literal["true", "false", "skip"]
_SHORT: dict[str, ShortAnswer] = {
    "si": "true", "sí": "true", "positivo": "true", "positiva": "true",
    "no": "false", "negativo": "false", "negativa": "false",
    "no lo evalue": "skip", "no evaluado": "skip", "no se": "skip", "no lo se": "skip",
}


def short_answer(text: str) -> ShortAnswer | None:
    """Deterministic short-answer classifier (SPECS §6.1), applied before any extractor."""
    t = normalize(text).strip(" .,!¡?¿")
    return _SHORT.get(t)


def delta_value(d: DeltaOut) -> FieldValue | None:
    """The value slot matching the key's catalog type."""
    ftype = load_catalog().get(d.key).type
    slot = {"bool": d.value_bool, "int": d.value_int, "enum": d.value_enum,
            "str": d.value_text, "float": d.value_text}[ftype]
    return slot


# ------------------------------------------------------------------- systems


@dataclass
class Stats:
    latencies_ms: list[float] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    dropped: list[str] = field(default_factory=list)


class System(Protocol):
    name: str

    async def step(self, history: list[Turn], turn: Turn, state: Fields,
                   pending: Question | None, stats: Stats) -> Fields: ...


class BaselineSystem:
    name = "baseline"

    async def step(self, history: list[Turn], turn: Turn, state: Fields,
                   pending: Question | None, stats: Stats) -> Fields:
        t0 = time.perf_counter()
        out = baseline.extract(turn.text)
        stats.latencies_ms.append((time.perf_counter() - t0) * 1000)
        return out


class CallBudgetExceeded(RuntimeError):
    pass


class MuseSystem:
    name = "muse"

    def __init__(self, extractor: Extractor, max_calls: int | None) -> None:
        self._extractor = extractor
        self._max_calls = max_calls
        self.calls = 0

    async def step(self, history: list[Turn], turn: Turn, state: Fields,
                   pending: Question | None, stats: Stats) -> Fields:
        if self._max_calls is not None and self.calls >= self._max_calls:
            raise CallBudgetExceeded(f"MUSE_MAX_LIVE_CALLS={self._max_calls} reached")
        self.calls += 1
        catalog = load_catalog()
        ctx = ExtractCtx(turns=list(history), new_turn=turn, catalog_keys=catalog.keys,
                         current_values=dict(state), pending_question=pending)
        t0 = time.perf_counter()
        out = await self._extractor.extract(ctx)
        stats.latencies_ms.append((time.perf_counter() - t0) * 1000)
        stats.tokens_in += len(ctx.model_dump_json()) // CHARS_PER_TOKEN
        stats.tokens_out += len(out.model_dump_json()) // CHARS_PER_TOKEN

        fields: Fields = {}
        turn_norm = normalize(turn.text)
        for d in out.deltas:
            if d.key not in catalog.keys:
                stats.dropped.append(f"{d.key}: unknown key")
                continue
            if not d.quote.strip() or normalize(d.quote) not in turn_norm:  # E-quote
                stats.dropped.append(f"{d.key}: quote not in turn")
                continue
            value = delta_value(d)
            err = check_value(d.key, value)
            if err:
                stats.dropped.append(err)
                continue
            assert value is not None
            fields.pop(d.key, None)
            fields[d.key] = value
        return fields


# -------------------------------------------------------------------- running


def _question(key: str) -> Question:
    f = load_catalog().get(key)
    return Question(id=f"q-{key}", key=key, text_es=f"¿{f.label_es}?", text_en=f"{f.label_en}?",
                    reason="bench scripted answer", impact=0, status="pending")


def _steps(case: dict[str, Any]) -> list[tuple[Turn, str | None]]:
    """Dictation turns, then each scripted answer as a turn with its question pending."""
    turns = [Turn(**t) for t in case["turns"]]
    out: list[tuple[Turn, str | None]] = [(t, None) for t in turns]
    tid = max((t.turn_id for t in turns), default=0)
    clock = max((t.end_ms for t in turns), default=0)
    for key, text in case["answers"].items():
        tid += 1
        clock += 2000
        out.append((Turn(turn_id=tid, start_ms=clock, end_ms=clock + 1500, text=text), key))
    return out


def planned_model_calls(cases: list[dict[str, Any]]) -> int:
    """Extractor calls the Muse system will make (short bool answers need none)."""
    n = 0
    for case in cases:
        for turn, key in _steps(case):
            sa = short_answer(turn.text) if key else None
            resolved = sa == "skip" or (sa is not None and load_catalog().get(key or "").type
                                        == "bool")
            n += 0 if resolved else 1
    return n


_BENCH_EVIDENCE = Evidence(source="dictated", quote=None, turn_id=None, start_ms=None,
                           document_id=None, confidence_pct=100)


class QuestionTracker:
    """Runs the 1A planner (`api.listen.planner.plan`) over the extracted fields,
    the way the session does: plan when no question is pending (also before the
    first turn), a question closes when its key gets a value or a scripted
    answer for it arrives. The dictation input itself is unchanged (replay keys
    stay the same); this only counts what the planner would have asked."""

    def __init__(self) -> None:
        self.questions: list[Question] = []

    def pending(self) -> Question | None:
        return next((q for q in self.questions if q.status == "pending"), None)

    def answer(self, key: str, skipped: bool) -> None:
        q = self.pending()
        if q is not None and key in procedure_keys(q.key):
            q.status = "skipped" if skipped else "answered"

    def update(self, state: Fields) -> None:
        fields: dict[str, FieldState] = {k: new_field(k, v, _BENCH_EVIDENCE)
                                         for k, v in state.items()}
        q = self.pending()
        if q is not None and q.key in fields:
            q.status = "answered"
        red_flag = bool(evaluate_fields(state).red_flag_ids)
        p = plan(fields, self.questions, red_flag)
        if p is not None:
            self.questions.append(to_question(p, f"q{len(self.questions) + 1}"))

    @property
    def asked(self) -> list[str]:
        return [q.key for q in self.questions]


async def run_case(system: System, case: dict[str, Any], stats: Stats,
                   tracker: QuestionTracker | None = None) -> Fields:
    state: Fields = {}
    history: list[Turn] = []
    tracker = tracker or QuestionTracker()
    tracker.update(state)
    for turn, key in _steps(case):
        if key is not None:
            sa = short_answer(turn.text)
            tracker.answer(key, skipped=sa == "skip")
            if sa == "skip":
                history.append(turn)
                tracker.update(state)
                continue
            if sa is not None and load_catalog().get(key).type == "bool":
                state[key] = sa == "true"
                history.append(turn)
                tracker.update(state)
                continue
        update = await system.step(history, turn,
                                   state, _question(key) if key else None, stats)
        state.update(update)
        history.append(turn)
        tracker.update(state)
    return state


def score_case(case: dict[str, Any], pred: Fields) -> dict[str, Any]:
    gold = case["gold"]
    gold_fields: Fields = gold["fields"]
    gold_r = evaluate_fields(gold_fields)
    r = evaluate_fields(pred)
    per_key = {k: values_equal(k, pred.get(k), v) for k, v in gold_fields.items()}
    negatives = {k: per_key[k] for k, v in gold_fields.items() if is_negative_gold(k, v)}
    flips = sorted(k for k, v in gold_fields.items() if v is False and pred.get(k) is True)
    gold_flags = set(gold_r.red_flag_ids)
    pred_urgency = r.urgency
    gold_urgency = Urgency(gold["urgency"])
    return {
        "predicted_fields": pred,
        "per_key_correct": per_key,
        "n_gold_keys": len(gold_fields),
        "n_correct": sum(per_key.values()),
        "n_predicted_keys": len(pred),
        "missing": sorted(k for k in gold_fields if k not in pred),
        "wrong": sorted(k for k in gold_fields if k in pred and not per_key[k]),
        "extra": sorted(k for k in pred if k not in gold_fields),
        "n_gold_negatives": len(negatives),
        "n_negatives_correct": sum(negatives.values()),
        "negation_flips": flips,
        "gold_red_flags": sorted(gold_flags),
        "red_flags": list(r.red_flag_ids),
        "red_flags_found": sorted(gold_flags & set(r.red_flag_ids)),
        "urgency": pred_urgency.value,
        "urgency_agrees": pred_urgency == gold_urgency,
        "under_triage": under_triage(pred_urgency, gold_urgency),
        "top1_dx": top1(r),
        "top1_agrees": None if gold["top1_dx"] is None else top1(r) == gold["top1_dx"],
        "blocked_actions": sorted(r.blocked_actions),
    }


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def summarize(rows: list[dict[str, Any]], stats: Stats, *, billed: bool) -> dict[str, Any]:
    lat = stats.latencies_ms
    p_in = os.environ.get("BENCH_PRICE_IN_PER_MTOK")
    p_out = os.environ.get("BENCH_PRICE_OUT_PER_MTOK")
    cost: float | None = 0.0
    if billed:
        cost = (round((stats.tokens_in * float(p_in) + stats.tokens_out * float(p_out)) / 1e6, 4)
                if p_in and p_out else None)
    top1_rows = [r for r in rows if r["top1_agrees"] is not None]
    return {
        "key_accuracy": _ratio(sum(r["n_correct"] for r in rows),
                               sum(r["n_gold_keys"] for r in rows)),
        "key_precision": _ratio(sum(r["n_correct"] for r in rows),
                                sum(r["n_predicted_keys"] for r in rows)),
        "red_flag_recall": _ratio(sum(len(r["red_flags_found"]) for r in rows),
                                  sum(len(r["gold_red_flags"]) for r in rows)),
        "negation_accuracy": _ratio(sum(r["n_negatives_correct"] for r in rows),
                                    sum(r["n_gold_negatives"] for r in rows)),
        "negation_flips": sum(len(r["negation_flips"]) for r in rows),
        "urgency_agreement": _ratio(sum(r["urgency_agrees"] for r in rows), len(rows)),
        "under_triage": sum(r["under_triage"] for r in rows),
        "top1_agreement": _ratio(sum(bool(r["top1_agrees"]) for r in top1_rows), len(top1_rows)),
        "questions_asked": sum(len(r["questions"]) for r in rows),
        "questions_per_case": _ratio(sum(len(r["questions"]) for r in rows), len(rows)),
        "calls": len(lat),
        "latency_ms_mean": round(statistics.fmean(lat), 2) if lat else None,
        "latency_ms_p95": round(sorted(lat)[max(0, round(0.95 * len(lat)) - 1)], 2) if lat
        else None,
        "est_tokens_in": stats.tokens_in,
        "est_tokens_out": stats.tokens_out,
        "cost_usd": cost,
        "dropped_deltas": len(stats.dropped),
    }


def per_key_table(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        for k, ok in r["per_key_correct"].items():
            e = out.setdefault(k, {"n": 0, "correct": 0})
            e["n"] += 1
            e["correct"] += int(ok)
    return dict(sorted(out.items()))


def planner_available() -> bool:
    try:
        return importlib.util.find_spec("api.listen.planner") is not None
    except ModuleNotFoundError:
        return False


# -------------------------------------------------------------------- output


_METRICS: list[tuple[str, str]] = [
    ("key_accuracy", "Per-key accuracy"),
    ("key_precision", "Key precision"),
    ("red_flag_recall", "Red-flag recall"),
    ("negation_accuracy", "Negation accuracy"),
    ("negation_flips", "Negation flips (absent → present)"),
    ("urgency_agreement", "Urgency agreement vs gold"),
    ("under_triage", "Under-triaged cases"),
    ("top1_agreement", "Top-1 dx agreement"),
    ("questions_asked", "Questions asked (planner, total)"),
    ("questions_per_case", "Questions asked per case (mean)"),
    ("latency_ms_mean", "Latency per call, mean (ms)"),
    ("latency_ms_p95", "Latency per call, p95 (ms)"),
    ("cost_usd", "Cost estimate (USD)"),
]


def _fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.3f}" if v <= 1 else f"{v:.1f}"
    return str(v)


def build_table(report: dict[str, Any]) -> dict[str, Any]:
    s = report["systems"]
    return {
        "mode": report["mode"],
        "generated_at": report["generated_at"],
        "n_cases": report["n_cases"],
        "systems": {"baseline": "keyword baseline", "muse": report["muse_model"]},
        "summary": [{"metric": key, "label": label, "baseline": s["baseline"][key],
                     "muse": s["muse"][key]} for key, label in _METRICS],
        "cases": [{
            "id": c["id"], "title_es": c["title_es"], "title_en": c["title_en"],
            "gold_urgency": c["gold_urgency"],
            **{f"{name}_{m}": c["systems"][name][m] for name in SYSTEMS
               for m in ("urgency", "n_correct")},
            "n_gold_keys": c["systems"]["baseline"]["n_gold_keys"],
            "gold_red_flags": c["systems"]["baseline"]["gold_red_flags"],
            **{f"{name}_red_flags": c["systems"][name]["red_flags"] for name in SYSTEMS},
        } for c in report["cases"]],
    }


def render_md(table: dict[str, Any]) -> str:
    lines = [
        f"# Bench results — mode `{table['mode']}`",
        "",
        f"{table['n_cases']} scripted cases · generated {table['generated_at']} · "
        f"Muse extractor: `{table['systems']['muse']}`",
        "",
        "Synthetic, scripted dictations; not a clinical validation. See bench/README.md.",
        "",
        "| Metric | Keyword baseline | Muse |",
        "|---|---|---|",
    ]
    lines += [f"| {r['label']} | {_fmt(r['baseline'])} | {_fmt(r['muse'])} |"
              for r in table["summary"]]
    lines += ["", "| Case | Gold urgency | Baseline | Muse | Keys ✓ baseline | Keys ✓ Muse |",
              "|---|---|---|---|---|---|"]
    for c in table["cases"]:
        def mark(u: str) -> str:
            return u if u == c["gold_urgency"] else f"**{u}** ✗"
        lines.append(
            f"| {c['title_en']} | {c['gold_urgency']} | {mark(c['baseline_urgency'])} | "
            f"{mark(c['muse_urgency'])} | {c['baseline_n_correct']}/{c['n_gold_keys']} | "
            f"{c['muse_n_correct']}/{c['n_gold_keys']} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------- guard


class NetworkBlocked(ConnectionRefusedError):
    pass


@contextmanager
def network_blocked(active: bool = True) -> Iterator[None]:
    """While active, any non-UNIX socket connect raises (mock / replay never touch the net)."""
    if not active:
        yield
        return
    real = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection)

    def _ok(sock: socket.socket) -> bool:
        return sock.family == getattr(socket, "AF_UNIX", None)

    def connect(self: socket.socket, address: Any) -> None:
        if not _ok(self):
            raise NetworkBlocked("bench: network disabled in this MUSE_MODE")
        real[0](self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        if not _ok(self):
            raise NetworkBlocked("bench: network disabled in this MUSE_MODE")
        return real[1](self, address)

    def create_connection(*_a: Any, **_k: Any) -> socket.socket:
        raise NetworkBlocked("bench: network disabled in this MUSE_MODE")

    socket.socket.connect = connect  # type: ignore[method-assign,assignment]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign,assignment]
    socket.create_connection = create_connection
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex = real[0], real[1]  # type: ignore[method-assign]
        socket.create_connection = real[2]


def live_budget(planned: int) -> int:
    raw = os.environ.get("MUSE_MAX_LIVE_CALLS")
    if not raw or not raw.isdigit():
        raise SystemExit(f"refusing --mode live: planned {planned} calls; "
                         "set MUSE_MAX_LIVE_CALLS to at least that number")
    budget = int(raw)
    if planned > budget:
        raise SystemExit(f"refusing --mode live: planned {planned} calls > "
                         f"MUSE_MAX_LIVE_CALLS={budget}")
    return budget


# ----------------------------------------------------------------------- main


async def run(mode: MuseMode, case_ids: list[str] | None = None,
              out_dir: Path = RESULTS_DIR) -> dict[str, Any]:
    cases = load_cases()
    if case_ids:
        cases = [c for c in cases if c["id"] in case_ids]
    planned = planned_model_calls(cases)
    print(f"bench: {len(cases)} cases, mode={mode}, planned Muse extractor calls: {planned}")
    budget = live_budget(planned) if mode == "live" else None

    stats = {name: Stats() for name in SYSTEMS}
    rows: dict[str, list[dict[str, Any]]] = {name: [] for name in SYSTEMS}
    case_out: list[dict[str, Any]] = []
    with network_blocked(mode != "live"):
        try:
            providers = get_providers(mode)
        except NotImplementedError as exc:
            raise SystemExit(f"bench: {exc}") from exc
        systems: dict[str, System] = {"baseline": BaselineSystem(),
                                      "muse": MuseSystem(providers.extractor, budget)}
        for case in cases:
            entry: dict[str, Any] = {"id": case["id"], "title_es": case["title_es"],
                                     "title_en": case["title_en"],
                                     "gold_urgency": case["gold"]["urgency"], "systems": {}}
            for name, system in systems.items():
                tracker = QuestionTracker()
                pred = await run_case(system, case, stats[name], tracker)
                row = score_case(case, pred)
                row["questions"] = tracker.asked
                rows[name].append(row)
                entry["systems"][name] = row
            case_out.append(entry)

    summaries = {name: summarize(rows[name], stats[name], billed=(name == "muse"
                                                                    and mode != "mock"))
                 for name in SYSTEMS}
    report: dict[str, Any] = {
        "mode": mode,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "engine_version": engine_version(),
        "muse_model": providers.model_ids.get("extractor", "unknown"),
        "n_cases": len(cases),
        "planned_calls": planned,
        "planner": "api.listen.planner" if planner_available() else "unavailable",
        "systems": summaries,
        "per_key": {name: per_key_table(rows[name]) for name in SYSTEMS},
        "dropped_deltas": {name: stats[name].dropped for name in SYSTEMS},
        "cases": case_out,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{mode}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    table = build_table(report)
    (out_dir / "table.json").write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n")
    md = render_md(table)
    (out_dir / "table.md").write_text(md)
    print(md)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    ap.add_argument("--mode", choices=["mock", "replay", "live"],
                    default=os.environ.get("MUSE_MODE", "mock"))
    ap.add_argument("--cases", help="comma-separated case ids (default: all)")
    ap.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = ap.parse_args()
    ids = [s.strip() for s in args.cases.split(",")] if args.cases else None
    asyncio.run(run(args.mode, ids, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

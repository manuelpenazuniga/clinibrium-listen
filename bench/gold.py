"""Recompute gold urgency for every bench case (engine on the gold projection).

The gold urgency is never hand-labelled: it is `engine/adapter.py` evaluated on
the gold atomic fields, stored in the case file. `top1_dx` is a hand label; this
script reports where it disagrees with the engine's top-1 on the gold fields.

Usage:  uv run python bench/gold.py [--write]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT / "engine"), str(_ROOT)]  # as in scripts/gen_catalog.py

from bench.common import case_paths, evaluate_fields, top1  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="store the computed urgency")
    args = ap.parse_args()
    stale = 0
    for path in case_paths():
        case = json.loads(path.read_text())
        gold = case["gold"]
        r = evaluate_fields(gold["fields"])
        urgency = r.urgency.value
        dx = top1(r)
        flag = "" if gold["urgency"] == urgency else "  (stale)"
        stale += bool(flag)
        print(f"{case['id']:>3}  urgency={urgency:<12} red_flags={list(r.red_flag_ids)} "
              f"engine_top1={dx} gold_top1={gold['top1_dx']}{flag}")
        if args.write and flag:
            gold["urgency"] = urgency
            path.write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n")
    if stale and not args.write:
        print(f"{stale} case(s) with stale gold urgency; rerun with --write")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

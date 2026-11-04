"""Phase 0 smoke test against the real Meta Model API (SPECS §11.8). NOT run in CI.

  (a) GET  /v1/models                 → muse-spark-1.3, muse-wonder-1.0, muse-voice-transcribe-1.0
  (b) POST /v1/chat/completions       → strict json_schema call to muse-spark-1.3 returning
                                        {"deltas":[...]} (DeltaOut) for a Spanish sentence
  (c) POST /v1/asr/transcribe         → a ~5 s Spanish WAV returns Spanish text

Reads MODEL_API_KEY from the environment (or a gitignored .env). The key is never
printed. Writes a Markdown report with --write (default path docs/SMOKE.md).

  uv run python scripts/smoke_meta.py [--wav clip.wav] [--write docs/SMOKE.md]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "engine")]

from api.catalog import load_catalog, normalize  # noqa: E402
from api.listen.contracts import ExtractorOut, strict_json_schema  # noqa: E402

BASE_URL = os.environ.get("MODEL_API_BASE_URL", "https://api.meta.ai/v1")
EXPECTED_MODELS = ("muse-spark-1.3", "muse-wonder-1.0", "muse-voice-transcribe-1.0")
SENTENCE = "Paciente de 68 años, vértigo continuo hace 12 horas, sin diplopía."
SPOKEN = "Paciente de sesenta y ocho años, vértigo continuo hace doce horas, sin diplopía."
SMOKE_KEYS = ["age_years", "duration", "timing_pattern", "focal_signs.diplopia",
              "context.last_known_well_minutes_ago", "onset"]


def _api_key() -> str:
    key = os.environ.get("MODEL_API_KEY", "")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("MODEL_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("MODEL_API_KEY not set (env var or .env)")
    return key


def _scrub(text: str, key: str) -> str:
    return text.replace(key, "[REDACTED]") if key else text


def _body(r: httpx.Response, key: str, limit: int = 800) -> str:
    return _scrub(r.text[:limit], key)


# ------------------------------------------------------------------- (a)

def check_models(client: httpx.Client, key: str) -> dict[str, Any]:
    t0 = time.monotonic()
    r = client.get("/models")
    out: dict[str, Any] = {"status": r.status_code,
                           "latency_ms": round((time.monotonic() - t0) * 1000)}
    if r.status_code != 200:
        out.update(ok=False, error=_body(r, key))
        return out
    data = r.json()
    ids = sorted(m.get("id", "?") for m in data.get("data", data if isinstance(data, list) else []))
    out.update(models=ids, missing=[m for m in EXPECTED_MODELS if m not in ids],
               ok=all(m in ids for m in EXPECTED_MODELS))
    return out


# ------------------------------------------------------------------- (b)

def _extract_payload(effort: str | None) -> dict[str, Any]:
    cat = load_catalog()
    fields = [cat.get(k) for k in SMOKE_KEYS]
    spec = "\n".join(
        f"- {f.key} ({f.type}{': ' + '|'.join(f.enum_values) if f.enum_values else ''})"
        for f in fields)
    payload: dict[str, Any] = {
        "model": "muse-spark-1.3",
        "messages": [
            {"role": "system", "content": (
                "You extract clinical findings from a Spanish physician dictation into "
                "catalog keys. Only what is stated. Copy `quote` verbatim from the text. "
                "Negated findings give false. Put the value in exactly one value_* slot "
                "(bool→value_bool, int→value_int, enum→value_enum, text→value_text); "
                "the others are null. answers_question_id is null.\nAllowed keys:\n" + spec)},
            {"role": "user", "content": SENTENCE},
        ],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "extractor_out", "schema": strict_json_schema(ExtractorOut), "strict": True}},
    }
    if effort:
        payload["reasoning_effort"] = effort
    return payload


def check_strict_extract(client: httpx.Client, key: str) -> dict[str, Any]:
    out: dict[str, Any] = {"attempts": []}
    for effort in ("minimal", "low", None):
        t0 = time.monotonic()
        r = client.post("/chat/completions", json=_extract_payload(effort), timeout=60)
        att: dict[str, Any] = {"reasoning_effort": effort, "status": r.status_code,
                               "latency_ms": round((time.monotonic() - t0) * 1000)}
        out["attempts"].append(att)
        if r.status_code != 200:
            att["error"] = _body(r, key)
            continue
        body = r.json()
        content = body["choices"][0]["message"].get("content") or ""
        att["usage"] = body.get("usage")
        out["raw_content"] = content
        try:
            parsed = ExtractorOut.model_validate_json(content)
        except Exception as exc:  # noqa: BLE001 — report any schema mismatch
            out.update(ok=False, validation_error=str(exc)[:800])
            return out
        keys = set(load_catalog().keys)
        deltas = [d.model_dump() for d in parsed.deltas]
        bad_keys = [d["key"] for d in deltas if d["key"] not in keys]
        bad_quotes = [d["quote"] for d in deltas
                      if normalize(d["quote"]) not in normalize(SENTENCE)]
        diplopia = next((d for d in deltas if d["key"] == "focal_signs.diplopia"), None)
        out.update(ok=not bad_keys, deltas=deltas, unknown_keys=bad_keys,
                   non_verbatim_quotes=bad_quotes,
                   diplopia_false=(diplopia is not None and diplopia["value_bool"] is False),
                   model=body.get("model"))
        return out
    out["ok"] = False
    return out


# ------------------------------------------------------------------- (c)

def make_wav(path: Path) -> str:
    """~5 s Spanish speech, mono 16-bit 16 kHz (macOS `say` + `afconvert`)."""
    if platform.system() != "Darwin" or not shutil.which("say") or not shutil.which("afconvert"):
        sys.exit("no --wav given and cannot synthesize one (needs macOS say/afconvert)")
    listing = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    # Lines look like "Paulina   es_MX   # Hola…" or "Eddy (Spanish (Mexico)) es_MX # …".
    spanish = [line.split("#")[0].rsplit(None, 1)[0].strip() for line in listing.splitlines()
               if " es_" in line.split("#")[0]]
    preferred = ("Paulina", "Mónica", "Monica", "Juan", "Jorge", "Diego")
    voice = next((v for p in preferred for v in spanish if v == p), None) or next(
        (v for v in spanish if "Mexico" in v), None) or (spanish[0] if spanish else None)
    if voice is None:
        sys.exit("no Spanish macOS voice installed")
    aiff = path.with_suffix(".aiff")
    subprocess.run(["say", "-v", voice, "-r", "150", "-o", str(aiff), SPOKEN], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff),
                    str(path)], check=True)
    return voice


def check_asr(client: httpx.Client, key: str, wav: Path) -> dict[str, Any]:
    with wave.open(str(wav)) as w:
        info = {"channels": w.getnchannels(), "sample_width": w.getsampwidth(),
                "rate": w.getframerate(), "seconds": round(w.getnframes() / w.getframerate(), 2)}
    request = {"model": "muse-voice-transcribe-1.0", "languageBias": ["Spanish"]}
    t0 = time.monotonic()
    r = client.post("/asr/transcribe", timeout=120, files={
        "request": (None, json.dumps(request), "application/json"),
        "audio": (wav.name, wav.read_bytes(), "audio/wav"),
    })
    out: dict[str, Any] = {"wav": info, "request": request, "status": r.status_code,
                           "latency_ms": round((time.monotonic() - t0) * 1000)}
    if r.status_code != 200:
        out.update(ok=False, error=_body(r, key))
        return out
    body = r.json()
    out["response_keys"] = sorted(body) if isinstance(body, dict) else type(body).__name__
    turns = body.get("turns", []) if isinstance(body, dict) else []
    out["turns"] = turns
    text = " ".join(t.get("transcript", "") for t in turns)
    out.update(ok=bool(text.strip()), transcript=text,
               spanish_hits=[w for w in ("paciente", "vertigo", "horas", "diplopia")
                             if w in normalize(text)])
    return out


# ---------------------------------------------------------------- report

def render(report: dict[str, Any]) -> str:
    def j(x: Any) -> str:
        return "```json\n" + json.dumps(x, ensure_ascii=False, indent=2) + "\n```"

    a, b, c = report["models"], report["strict_extract"], report["asr_transcribe"]
    mark = {True: "✅ PASS", False: "❌ FAIL"}
    return "\n".join([
        "# Meta Model API smoke test (Phase 0)",
        "",
        f"Run: {report['run_at']} · base URL `{BASE_URL}` · script `scripts/smoke_meta.py`.",
        "Key read from `MODEL_API_KEY` (never logged).",
        "",
        "| Check | Result |", "|---|---|",
        f"| (a) `GET /v1/models` lists the 3 models | {mark[bool(a.get('ok'))]} |",
        f"| (b) strict `json_schema` → `{{\"deltas\":[...]}}` from muse-spark-1.3 | "
        f"{mark[bool(b.get('ok'))]} |",
        f"| (c) `POST /v1/asr/transcribe` returns Spanish text | {mark[bool(c.get('ok'))]} |",
        "",
        "## (a) Models", j(a),
        "", "## (b) Strict structured output", f"Input: `{SENTENCE}`", j(b),
        "", "## (c) File ASR", j(c),
        "", "## Corrections to SPECS §3.1", *report.get("corrections", ["- none observed"]),
        "",
    ])


def corrections(report: dict[str, Any]) -> list[str]:
    out: list[str] = []
    a, b, c = report["models"], report["strict_extract"], report["asr_transcribe"]
    if a.get("missing"):
        out.append(f"- Model IDs not listed: {a['missing']} (listed: {a.get('models')}).")
    failed = [x for x in b.get("attempts", []) if x["status"] != 200]
    for x in failed:
        out.append(f"- `reasoning_effort={x['reasoning_effort']}` → HTTP {x['status']}.")
    if c.get("status") and c["status"] != 200:
        out.append(f"- `/v1/asr/transcribe` returned HTTP {c['status']} with the documented "
                   "multipart shape; see body above.")
    elif c.get("response_keys") and "turns" not in c["response_keys"]:
        out.append(f"- ASR response keys are {c['response_keys']}, not `turns[]`.")
    return out or ["- none observed"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", type=Path)
    ap.add_argument("--write", type=Path, nargs="?", const=ROOT / "docs" / "SMOKE.md")
    args = ap.parse_args()
    key = _api_key()
    headers = {"Authorization": f"Bearer {key}"}
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        report: dict[str, Any] = {"run_at": datetime.now(UTC).isoformat(timespec="seconds")}
        report["models"] = check_models(client, key)
        report["strict_extract"] = check_strict_extract(client, key)
        with tempfile.TemporaryDirectory() as tmp:
            wav = args.wav
            if wav is None:
                wav = Path(tmp) / "smoke_es.wav"
                report["tts_voice"] = make_wav(wav)
            report["asr_transcribe"] = check_asr(client, key, wav)
    report["corrections"] = corrections(report)
    text = _scrub(json.dumps(report, ensure_ascii=False, indent=2), key)
    print(text)
    if args.write:
        args.write.parent.mkdir(exist_ok=True)
        args.write.write_text(_scrub(render(report), key))
        print(f"wrote {args.write}", file=sys.stderr)
    ok = all(report[k].get("ok") for k in ("models", "strict_extract", "asr_transcribe"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Muse client: budget guard (fail closed), ledger, retries, recording, hashing."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from api.listen.contracts import PhrasingOut
from api.muse import client as cl
from api.muse.client import (
    SPARK,
    WONDER,
    BudgetExceeded,
    BudgetGuard,
    ChatRequest,
    LiveTransport,
    MuseClient,
    MuseSchemaError,
    QuotaStop,
    prompt_hashes,
    replay_key,
)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for k in ("MUSE_MAX_LIVE_CALLS", "MUSE_MAX_WONDER_CALLS", "MUSE_MAX_VISION_CALLS",
              "MUSE_RECORD", "MUSE_REPLAY_CASE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MUSE_USAGE_LEDGER", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setattr(cl, "REPLAYS_DIR", tmp_path / "replays")


def _req(model: str = SPARK, image: bool = False, role: str = "phraser") -> ChatRequest:
    return ChatRequest(role=role, model=model,  # type: ignore[arg-type]
                       messages=[{"role": "user", "content": "x"}], schema_name="p",
                       schema={}, max_completion_tokens=10, reasoning_effort="minimal",
                       replay_key="k" * 64, has_image=image)


class FakeSDK:
    """Stands in for AsyncOpenAI: pops scripted outcomes."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kw: Any) -> Any:
        self.calls.append(kw)
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


def _ok(content: str) -> Any:
    usage = SimpleNamespace(prompt_tokens=400, completion_tokens=600,
                            completion_tokens_details=SimpleNamespace(reasoning_tokens=300))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                           usage=usage)


def _http(status: int, msg: str = "err", headers: dict[str, str] | None = None) -> Exception:
    resp = httpx.Response(status, headers=headers or {},
                          request=httpx.Request("POST", "https://api.meta.ai/v1/x"))
    return openai.APIStatusError(msg, response=resp, body=None)


async def _nosleep(_s: float) -> None:
    return None


PHRASE = json.dumps({"text_es": "¿Hola?", "text_en": "Hi?"})


# ----------------------------------------------------------------- guard


@pytest.mark.parametrize("value", [None, "", "0", "abc"])
def test_guard_fails_closed_when_unset_or_zero(monkeypatch: pytest.MonkeyPatch,
                                               value: str | None) -> None:
    if value is not None:
        monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", value)
    with pytest.raises(BudgetExceeded):
        BudgetGuard().check(_req())


def test_guard_wonder_needs_its_own_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "5")
    BudgetGuard().check(_req(SPARK))
    with pytest.raises(BudgetExceeded):
        BudgetGuard().check(_req(WONDER))
    monkeypatch.setenv("MUSE_MAX_WONDER_CALLS", "1")
    BudgetGuard().check(_req(WONDER))


def test_guard_counts_from_ledger_and_exhausts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "2")
    monkeypatch.setenv("MUSE_MAX_WONDER_CALLS", "1")
    g = BudgetGuard()
    g.record(_req(WONDER), {}, 1, "ok")
    with pytest.raises(BudgetExceeded, match="WONDER"):
        g.check(_req(WONDER))
    g.check(_req(SPARK))
    g.record(_req(SPARK), {}, 1, "ok")
    with pytest.raises(BudgetExceeded, match="LIVE"):
        BudgetGuard().check(_req(SPARK))  # a fresh guard (new process) sees the ledger


def test_guard_vision_cap_never_above_10(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "100")
    monkeypatch.setenv("MUSE_MAX_VISION_CALLS", "50")
    g = BudgetGuard()
    for _ in range(10):
        g.record(_req(image=True, role="vision"), {}, 1, "ok")
    with pytest.raises(BudgetExceeded, match="vision"):
        g.check(_req(image=True, role="vision"))
    g.check(_req())


def test_ledger_rows_have_no_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    BudgetGuard().record(_req(), {"prompt_tokens": 1, "completion_tokens": 2,
                                  "reasoning_tokens": 3}, 7, "ok")
    row = json.loads((tmp_path / "ledger.jsonl").read_text())
    assert set(row) == {"ts", "role", "model", "prompt_tokens", "completion_tokens",
                        "reasoning_tokens", "latency_ms", "status"}


# ------------------------------------------------------------- transport


async def test_live_disabled_never_touches_sdk() -> None:
    sdk = FakeSDK([_ok(PHRASE)])
    with pytest.raises(BudgetExceeded):
        await LiveTransport(sdk=sdk, sleep=_nosleep).send(_req())
    assert sdk.calls == []


async def test_live_ok_ledgers_usage_and_sets_limits(monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Path) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "3")
    sdk = FakeSDK([_ok(PHRASE)])
    out = await MuseClient(LiveTransport(sdk=sdk, sleep=_nosleep)).complete(
        role="phraser", model=SPARK, system="s", user={"a": 1}, out=PhrasingOut,
        key_inputs={"a": 1}, prompt_name="phrasing")
    assert out.text_es == "¿Hola?"
    kw = sdk.calls[0]
    assert kw["max_completion_tokens"] == 1000 and kw["reasoning_effort"] == "minimal"
    assert kw["response_format"]["json_schema"]["strict"] is True
    row = json.loads((tmp_path / "ledger.jsonl").read_text())
    assert (row["prompt_tokens"], row["completion_tokens"], row["reasoning_tokens"]) == (
        400, 600, 300)
    assert not (tmp_path / "replays").exists()  # MUSE_RECORD unset → no recording


async def test_retries_are_bounded_then_stop(monkeypatch: pytest.MonkeyPatch,
                                             tmp_path: Path) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "50")
    sleeps: list[float] = []

    async def sleep(s: float) -> None:
        sleeps.append(s)

    sdk = FakeSDK([_http(503)] * 10)
    t = LiveTransport(sdk=sdk, sleep=sleep)
    with pytest.raises(QuotaStop):
        await t.send(_req())
    assert len(sdk.calls) == 4 and len(sleeps) == 3  # 1 try + 3 retries
    with pytest.raises(QuotaStop):  # latched: no further live calls
        await t.send(_req())
    assert len(sdk.calls) == 4
    assert len((tmp_path / "ledger.jsonl").read_text().splitlines()) == 4


async def test_retry_after_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "50")
    sleeps: list[float] = []

    async def sleep(s: float) -> None:
        sleeps.append(s)

    sdk = FakeSDK([_http(429, headers={"retry-after": "7"}), _ok(PHRASE)])
    await LiveTransport(sdk=sdk, sleep=sleep).send(_req())
    assert sleeps and sleeps[0] >= 7


@pytest.mark.parametrize("exc", [_http(402), _http(400, "insufficient quota")])
async def test_billing_errors_stop_immediately(monkeypatch: pytest.MonkeyPatch,
                                               exc: Exception) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "50")
    sdk = FakeSDK([exc, _ok(PHRASE)])
    with pytest.raises(QuotaStop):
        await LiveTransport(sdk=sdk, sleep=_nosleep).send(_req())
    assert len(sdk.calls) == 1


async def test_budget_checked_on_every_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "2")
    sdk = FakeSDK([_http(500)] * 5)
    with pytest.raises(BudgetExceeded):
        await LiveTransport(sdk=sdk, sleep=_nosleep).send(_req())
    assert len(sdk.calls) == 2


async def test_schema_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "3")
    sdk = FakeSDK([_ok('{"text_es": "x"}')])
    with pytest.raises(MuseSchemaError):
        await MuseClient(LiveTransport(sdk=sdk, sleep=_nosleep)).complete(
            role="phraser", model=SPARK, system="s", user="u", out=PhrasingOut,
            key_inputs="u", prompt_name="phrasing")


async def test_record_writes_redacted_fixture(monkeypatch: pytest.MonkeyPatch,
                                              tmp_path: Path) -> None:
    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "3")
    monkeypatch.setenv("MUSE_RECORD", "1")
    monkeypatch.setenv("MUSE_REPLAY_CASE", "T")
    monkeypatch.setenv("MODEL_API_KEY", "sk-test-secret-value")
    sdk = FakeSDK([_ok(PHRASE)])
    await MuseClient(LiveTransport(sdk=sdk, sleep=_nosleep)).complete(
        role="vision", model=SPARK, system="s", user="u", out=PhrasingOut, key_inputs="u",
        prompt_name="vision", image_data_url="data:image/png;base64,QUJD")
    files = list((tmp_path / "replays" / "T").glob("*.json"))
    assert len(files) == 1
    raw = files[0].read_text()
    assert "QUJD" not in raw and "sk-test-secret-value" not in raw
    assert json.loads(raw)["response"]["content"] == PHRASE


# ----------------------------------------------------------------- hashing


def test_replay_key_is_stable_and_sensitive() -> None:
    a = replay_key("extractor", SPARK, "extractor", {"x": 1, "y": [1, 2]})
    assert a == replay_key("extractor", SPARK, "extractor", {"y": [1, 2], "x": 1})
    assert a != replay_key("extractor", WONDER, "extractor", {"x": 1, "y": [1, 2]})
    assert a != replay_key("extractor", SPARK, "extractor", {"x": 2, "y": [1, 2]})


def test_prompt_hashes_cover_every_role() -> None:
    h = prompt_hashes()
    assert set(h) == {"extractor", "phrasing", "advocate", "vision", "reasoner"}
    assert all(len(v) == 64 for v in h.values())


def test_prompt_change_changes_replay_key(monkeypatch: pytest.MonkeyPatch) -> None:
    a = replay_key("phraser", SPARK, "phrasing", {"k": 1})
    monkeypatch.setattr(cl, "prompt_sha256", lambda name: "0" * 64)
    assert replay_key("phraser", SPARK, "phrasing", {"k": 1}) != a


def test_no_secret_in_prompts_or_fixtures() -> None:
    root = Path(cl.ROOT)
    for p in [*(root / "api/muse/prompts").glob("*.md"),
              *(root / "fixtures/replays").rglob("*.json")]:
        text = p.read_text(encoding="utf-8")
        assert "Bearer " not in text and "MODEL_API_KEY" not in text, p


async def test_cancelled_in_flight_call_still_counts_against_the_caps(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A caller timeout (asyncio.wait_for) cancels a request Meta may still bill:
    it must leave a ledger row so the fail-closed caps see it (Phase 2b finding)."""
    import asyncio

    monkeypatch.setenv("MUSE_MAX_LIVE_CALLS", "1")

    class SlowSDK(FakeSDK):
        async def _create(self, **kw: Any) -> Any:
            self.calls.append(kw)
            await asyncio.sleep(10)

    t = LiveTransport(sdk=SlowSDK([]), sleep=_nosleep)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(t.send(_req()), 0.05)
    rows = [json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert [r["status"] for r in rows] == ["cancelled"]
    with pytest.raises(BudgetExceeded):
        BudgetGuard().check(_req())

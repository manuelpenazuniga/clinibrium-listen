"""Verifiable receipt (SPECS §7 receipt.py, L8). Pure.

Canonical JSON = `json.dumps(sort_keys=True, separators=(",", ":"),
ensure_ascii=False)` over a payload that contains NO floats (checked, fails
closed). `sha256` is the hex digest of the UTF-8 bytes of that exact string,
so the browser can verify it with WebCrypto over the delivered
`canonical_json`.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from api.listen.contracts import EngineResultView, FieldValue, Receipt, Turn

RECEIPT_VERSION = 1


class FloatInReceipt(TypeError):
    pass


def _check(node: Any, path: str = "$") -> None:
    if isinstance(node, float):
        raise FloatInReceipt(f"float at {path}")
    if isinstance(node, dict):
        for k, v in node.items():
            if not isinstance(k, str):
                raise TypeError(f"non-str key at {path}")
            _check(v, f"{path}.{k}")
    elif isinstance(node, list | tuple):
        for i, v in enumerate(node):
            _check(v, f"{path}[{i}]")
    elif isinstance(node, set | frozenset):
        raise TypeError(f"set at {path}: sort it first")
    elif node is not None and not isinstance(node, str | int | bool):
        raise TypeError(f"unsupported {type(node).__name__} at {path}")


def canonical_json(payload: Mapping[str, Any]) -> str:
    _check(dict(payload))
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def receipt_payload(*, session_id: str, snapshot: int, turns: Sequence[Turn],
                    confirmed: Mapping[str, FieldValue], result: EngineResultView,
                    clinician_actions: Sequence[Mapping[str, Any]],
                    model_ids: Mapping[str, str], prompt_hashes: Mapping[str, str],
                    created_at: str) -> dict[str, Any]:
    return {
        "receipt_version": RECEIPT_VERSION,
        "session_id": session_id,
        "snapshot": snapshot,
        "created_at": created_at,
        "turn_sha256": [sha256_hex(t.text) for t in turns],
        "confirmed": dict(sorted(confirmed.items())),
        "result": result.model_dump(mode="json"),
        "clinician_actions": [dict(a) for a in clinician_actions],
        "model_ids": dict(sorted(model_ids.items())),
        "prompt_hashes": dict(sorted(prompt_hashes.items())),
        "engine_version": result.engine_version,
    }


def build_receipt(**kw: Any) -> Receipt:
    payload = receipt_payload(**kw)
    cj = canonical_json(payload)
    return Receipt(canonical_json=cj, sha256=sha256_hex(cj), snapshot=kw["snapshot"],
                   created_at=kw["created_at"])


def verify(receipt: Receipt) -> bool:
    return sha256_hex(receipt.canonical_json) == receipt.sha256


__all__ = ["FloatInReceipt", "build_receipt", "canonical_json", "receipt_payload", "sha256_hex",
           "verify"]

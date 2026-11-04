"""Dump every model of api/listen/contracts.py as ONE JSON Schema (for json2ts)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "engine")]

from pydantic import BaseModel  # noqa: E402
from pydantic.json_schema import models_json_schema  # noqa: E402

from api.listen import contracts  # noqa: E402


def _strip_property_titles(node: Any, is_definition: bool = False) -> Any:
    """Keep model titles (interface names); drop per-property titles, which
    json2ts would otherwise turn into one type alias per property."""
    if isinstance(node, list):
        return [_strip_property_titles(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {k: _strip_property_titles(v) for k, v in node.items()
           if not (k == "title" and not is_definition)}
    if "properties" in node:
        out["properties"] = {k: _strip_property_titles(v) for k, v in node["properties"].items()}
    return out


def main() -> None:
    models = sorted(
        (m for m in vars(contracts).values()
         if isinstance(m, type) and issubclass(m, BaseModel) and m.__module__ == contracts.__name__
         and not m.__name__.startswith("_")),
        key=lambda m: m.__name__,
    )
    _, top = models_json_schema([(m, "serialization") for m in models],
                                ref_template="#/definitions/{model}")
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "ClinibriumListenContracts",
        "type": "object",
        "additionalProperties": False,
        "properties": {m.__name__: {"$ref": f"#/definitions/{m.__name__}"} for m in models},
        "definitions": {name: _strip_property_titles(d, is_definition=True)
                        for name, d in top["$defs"].items()},
    }
    json.dump(schema, sys.stdout, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()

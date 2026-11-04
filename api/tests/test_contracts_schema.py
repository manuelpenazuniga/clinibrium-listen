"""Phase 0 contracts: strict-JSON compatibility and extra='forbid'."""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from api.listen import contracts as c


@pytest.mark.parametrize("model", c.MODEL_OUTPUT_MODELS, ids=lambda m: m.__name__)
def test_model_output_schemas_are_strict(model: type[BaseModel]) -> None:
    schema = c.strict_json_schema(model)
    assert schema["type"] == "object"
    assert "$ref" not in str(schema) and "$defs" not in schema


def test_every_contract_forbids_extra_keys() -> None:
    models = [v for v in vars(c).values()
              if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == c.__name__]
    assert len(models) >= 25
    for m in models:
        assert m.model_config.get("extra") == "forbid", m.__name__


def test_delta_out_rejects_unknown_keys_and_missing_fields() -> None:
    ok = {"key": "focal_signs.diplopia", "value_bool": False, "value_int": None,
          "value_enum": None, "value_text": None, "quote": "sin diplopía",
          "confidence_pct": 90, "answers_question_id": None}
    c.DeltaOut.model_validate(ok)
    with pytest.raises(ValidationError):
        c.DeltaOut.model_validate({**ok, "urgency": "inmediata"})  # L3: no urgency channel
    with pytest.raises(ValidationError):
        c.DeltaOut.model_validate({k: v for k, v in ok.items() if k != "value_int"})


def test_no_float_typed_fields_in_contracts() -> None:
    def walk(node: object) -> None:
        if isinstance(node, dict):
            assert node.get("type") != "number", node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(c.SessionState.model_json_schema())
    for m in c.MODEL_OUTPUT_MODELS:
        walk(m.model_json_schema())


def test_strict_schema_rejects_optional_with_default() -> None:
    class Loose(BaseModel):
        model_config = {"extra": "forbid"}
        a: int | None = None

    with pytest.raises(ValueError, match="required"):
        c.strict_json_schema(Loose)

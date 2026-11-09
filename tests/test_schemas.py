import json

import pytest
from pydantic import ValidationError

from triage.schemas import Triage

VALID = {
    "topic": "technical_issue",
    "urgency": "high",
    "needs_human": True,
    "explanation": "The submission site is down close to a deadline.",
}


def test_valid_json_parses():
    triage = Triage.model_validate_json(json.dumps(VALID))

    assert triage.topic == "technical_issue"
    assert triage.urgency == "high"
    assert triage.needs_human is True
    assert triage.explanation == "The submission site is down close to a deadline."


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("topic", "homework"),
        ("urgency", "urgent"),
        ("needs_human", "maybe"),
        ("explanation", ""),
        ("confidence", 0.9),
    ],
)
def test_bad_output_is_rejected(field, value):
    bad = {**VALID, field: value}

    with pytest.raises(ValidationError):
        Triage.model_validate_json(json.dumps(bad))


def test_missing_field_is_rejected():
    missing = {key: value for key, value in VALID.items() if key != "urgency"}

    with pytest.raises(ValidationError):
        Triage.model_validate_json(json.dumps(missing))


def test_schema_lists_labels_inline():
    schema = Triage.model_json_schema()

    assert "$ref" not in json.dumps(schema)
    assert schema["properties"]["urgency"]["enum"] == ["low", "medium", "high"]
    assert schema["additionalProperties"] is False

import json

import pytest

from triage.classifier import TriageError, classify
from triage.llm import FakeClient, LLMError

QUESTION = "The submission site is down and my project is due in one hour."


def no_sleep(seconds):
    pass


def good_reply(**overrides):
    return json.dumps(
        {
            "topic": "technical_issue",
            "urgency": "low",
            "needs_human": False,
            "explanation": "The submission system is broken.",
            **overrides,
        }
    )


def test_valid_first_reply_is_returned():
    client = FakeClient([good_reply()])

    result = classify(QUESTION, client, sleep=no_sleep)

    assert result.topic == "technical_issue"
    assert len(client.calls) == 1
    assert client.calls[0][0]["role"] == "system"


def test_invalid_reply_is_retried_with_the_error():
    client = FakeClient(["not json at all", good_reply()])

    classify(QUESTION, client, sleep=no_sleep)

    assert len(client.calls) == 2
    second_call = client.calls[1]
    assert second_call[-2] == {"role": "assistant", "content": "not json at all"}
    assert "did not match the schema" in second_call[-1]["content"]


def test_gives_up_after_max_attempts():
    client = FakeClient([good_reply(topic="homework") for _ in range(3)])

    with pytest.raises(TriageError) as exc_info:
        classify(QUESTION, client, sleep=no_sleep)

    assert exc_info.value.attempts == 3
    assert len(client.calls) == 3


def test_network_error_backs_off_then_succeeds():
    client = FakeClient([LLMError("connection refused"), good_reply()])
    waits = []

    classify(QUESTION, client, sleep=waits.append)

    assert waits == [1]


def test_high_urgency_always_needs_a_human():
    client = FakeClient([good_reply(urgency="high", needs_human=False)])

    result = classify(QUESTION, client, sleep=no_sleep)

    assert result.needs_human is True

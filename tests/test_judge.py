import json

import pytest

from triage.judge import (
    JUDGE_PROMPT,
    JudgeError,
    build_judge_messages,
    judge_explanation,
)
from triage.llm import FakeClient, LLMError
from triage.schemas import Triage

QUESTION = "My submission portal says 403 forbidden and the assignment is due in 2 hours."
RESULT = Triage(
    topic="technical_issue",
    urgency="high",
    needs_human=True,
    explanation="The portal is blocking a submission that is due very soon.",
)


def verdict(grounded, consistent, reason="Checked against the question."):
    return json.dumps({"grounded": grounded, "consistent": consistent, "reason": reason})


def test_judge_sees_question_labels_and_explanation():
    user_message = build_judge_messages(QUESTION, RESULT)[1]["content"]

    assert QUESTION in user_message
    assert "topic=technical_issue" in user_message
    assert "needs_human=true" in user_message
    assert RESULT.explanation in user_message


@pytest.mark.parametrize(
    ("grounded", "consistent", "passed"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_passes_only_when_grounded_and_consistent(grounded, consistent, passed):
    client = FakeClient([verdict(grounded, consistent)])

    result = judge_explanation(QUESTION, RESULT, client)

    assert result.passed is passed


@pytest.mark.parametrize("reply", ["not json", LLMError("down")])
def test_bad_reply_or_call_failure_is_judge_error(reply):
    client = FakeClient([reply])

    with pytest.raises(JudgeError):
        judge_explanation(QUESTION, RESULT, client)


def test_judge_prompt_is_the_system_message():
    messages = build_judge_messages(QUESTION, RESULT)

    assert messages[0] == {"role": "system", "content": JUDGE_PROMPT}

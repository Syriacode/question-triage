from pydantic import BaseModel, ConfigDict, Field, ValidationError

from triage.classifier import describe_errors
from triage.llm import LLMClient, LLMError, Message
from triage.schemas import Triage

JUDGE_PROMPT = """\
You grade the explanation that a triage assistant wrote for its decision about a question sent to
a university course's help inbox. You do not decide the labels yourself. Reply with JSON only,
matching the given schema.

grounded:
- true: every fact the explanation states is in the question
- false: it invents details (a deadline, an error message, a feeling, a course name) the question
  doesn't contain

consistent:
- true: the explanation supports the labels it was given (topic, urgency, needs_human)
- false: it argues for different labels or contradicts them

reason: one short sentence.
"""


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grounded: bool
    consistent: bool
    reason: str = Field(min_length=1, max_length=300)

    @property
    def passed(self) -> bool:
        return self.grounded and self.consistent


class JudgeError(Exception):
    """The judge did not return a valid verdict."""


def build_judge_messages(question: str, result: Triage) -> list[Message]:
    needs_human = "true" if result.needs_human else "false"
    return [
        {"role": "system", "content": JUDGE_PROMPT},
        {
            "role": "user",
            "content": f"Question:\n{question}\n\n"
            f"Labels: topic={result.topic}, urgency={result.urgency}, "
            f"needs_human={needs_human}\n"
            f"Explanation:\n{result.explanation}",
        },
    ]


def judge_explanation(question: str, result: Triage, client: LLMClient) -> JudgeVerdict:
    messages = build_judge_messages(question, result)
    try:
        response = client.chat(messages, schema=JudgeVerdict.model_json_schema(), temperature=0.0)
    except LLMError as err:
        raise JudgeError(str(err)) from err
    try:
        return JudgeVerdict.model_validate_json(response.text)
    except ValidationError as err:
        raise JudgeError(f"invalid verdict: {describe_errors(err)}") from err

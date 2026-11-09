import time
from collections.abc import Callable

from pydantic import ValidationError

from triage.llm import LLMClient, LLMError, Message
from triage.schemas import Triage
from triage.usage_log import UsageLog

SYSTEM_PROMPT = """\
You triage questions sent to a university course's help inbox, from students or people using
the course website. Reply with JSON only, matching the given schema.

topic:
- course_content: explaining lecture or reading material
- assignment_help: how to approach or fix their homework or project
- deadlines_extensions: due dates, late work, extension requests
- grading_policy: how work is graded, regrade requests, grade disputes
- technical_issue: course website, submission system or software is broken
- account_access: login, password, enrollment, permissions
- other: anything else

urgency:
- high: it blocks the student right now, a deadline is within 24 hours, or it mentions a health,
  safety or personal emergency
- medium: it needs an answer within a few days
- low: otherwise

needs_human:
- true: the answer needs a decision only staff can make (extensions, regrades, exceptions,
  account changes) or the person seems upset or in distress
- false: a standard answer or pointer to course materials would do

explanation: one short sentence saying why.
"""


class TriageError(Exception):
    def __init__(self, attempts: int, last_error: str) -> None:
        super().__init__(f"no valid triage after {attempts} attempts: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


def build_messages(question: str) -> list[Message]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Question:\n{question}"},
    ]


def describe_errors(err: ValidationError) -> str:
    parts = []
    for error in err.errors(include_url=False):
        field = ".".join(str(part) for part in error["loc"]) or "reply"
        parts.append(f"{field}: {error['msg']}")
    return "; ".join(parts)


def apply_policy(result: Triage) -> Triage:
    if result.urgency == "high" and result.needs_human is False:
        return result.model_copy(update={"needs_human": True})
    return result


def classify(
    question: str,
    client: LLMClient,
    *,
    log: UsageLog | None = None,
    max_attempts: int = 3,
    temperature: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Triage:
    messages = build_messages(question)
    schema = Triage.model_json_schema()
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat(messages, schema=schema, temperature=temperature)
        except LLMError as err:
            last_error = str(err)
            if log:
                log.record(model=client.model, attempt=attempt, ok=False, error=last_error)
            if attempt < max_attempts:
                sleep(2 ** (attempt - 1))
            continue

        try:
            result = Triage.model_validate_json(response.text)
        except ValidationError as err:
            last_error = f"invalid output: {describe_errors(err)}"
            if log:
                log.record(
                    model=response.model,
                    attempt=attempt,
                    ok=False,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    latency_ms=response.latency_ms,
                    error=last_error,
                )
            messages = [
                *messages,
                {"role": "assistant", "content": response.text},
                {
                    "role": "user",
                    "content": "That reply did not match the schema: "
                    f"{last_error}. Reply again with JSON only.",
                },
            ]
            continue

        if log:
            log.record(
                model=response.model,
                attempt=attempt,
                ok=True,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=response.latency_ms,
            )

        return apply_policy(result)

    raise TriageError(max_attempts, last_error)

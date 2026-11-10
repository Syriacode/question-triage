from collections import Counter
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from triage.schemas import Topic, Urgency


class GoldenExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    question: str = Field(min_length=1)
    topic: Topic
    urgency: Urgency
    needs_human: bool
    hard: bool = False
    reviewed: bool = False

    @model_validator(mode="after")
    def high_urgency_needs_a_human(self) -> Self:
        if self.urgency == "high" and not self.needs_human:
            raise ValueError("urgency high requires needs_human true (the policy rule)")
        return self


def load_golden(path: Path, *, require_reviewed: bool = True) -> list[GoldenExample]:
    examples: list[GoldenExample] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            example = GoldenExample.model_validate_json(line)
        except ValidationError as err:
            raise ValueError(f"{path}:{line_number}: {err}") from err
        if require_reviewed and not example.reviewed:
            raise ValueError(f"{path}:{line_number}: {example.id} is not reviewed yet")
        examples.append(example)

    counts = Counter(example.id for example in examples)
    dupes = sorted(id_ for id_, count in counts.items() if count > 1)
    if dupes:
        raise ValueError(f"{path}: duplicate ids: {', '.join(dupes)}")
    return examples

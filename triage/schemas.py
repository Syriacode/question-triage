from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Topic = Literal[
    "course_content",
    "assignment_help",
    "deadlines_extensions",
    "grading_policy",
    "technical_issue",
    "account_access",
    "other",
]
Urgency = Literal["low", "medium", "high"]


class Triage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: Topic
    urgency: Urgency
    needs_human: bool
    explanation: str = Field(min_length=1, max_length=300)

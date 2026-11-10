import hashlib
import json
import time
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from triage import metrics
from triage.classifier import SYSTEM_PROMPT, TriageError, classify
from triage.llm import LLMClient
from triage.schemas import Topic, Triage, Urgency
from triage.usage_log import UsageLog

FIELDS = ("topic", "urgency", "needs_human")
ERROR = "ERROR"


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


def fingerprint(golden_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(SYSTEM_PROMPT.encode("utf-8"))
    digest.update(json.dumps(Triage.model_json_schema(), sort_keys=True).encode("utf-8"))
    digest.update(golden_path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:16]


def as_label(value: str | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


class RowResult(BaseModel):
    id: str
    question: str
    hard: bool
    gold: dict[str, str]
    pred: dict[str, str]
    explanation: str | None = None
    error: str | None = None
    judge_passed: bool | None = None
    judge_reason: str | None = None


class LabelRow(BaseModel):
    support: int
    precision: float
    recall: float


class EvalReport(BaseModel):
    fingerprint: str
    model: str
    judge_model: str | None
    created_at: str
    examples: int
    errors: int
    accuracy: dict[str, float]
    exact_match: float
    hard_exact_match: float
    per_label: dict[str, dict[str, LabelRow]]
    confusions: dict[str, list[tuple[str, str, int]]]
    judge_pass_rate: float | None
    rows: list[RowResult]


def run_eval(
    examples: Sequence[GoldenExample],
    client: LLMClient,
    *,
    fingerprint: str,
    log: UsageLog | None = None,
    on_row: Callable[[int, RowResult], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> EvalReport:
    rows: list[RowResult] = []
    for index, example in enumerate(examples, start=1):
        gold = {field: as_label(getattr(example, field)) for field in FIELDS}
        common = {"id": example.id, "question": example.question, "hard": example.hard}
        try:
            result = classify(example.question, client, log=log, sleep=sleep)
        except TriageError as err:
            row = RowResult(
                **common, gold=gold, pred={field: ERROR for field in FIELDS}, error=str(err)
            )
        else:
            pred = {field: as_label(getattr(result, field)) for field in FIELDS}
            row = RowResult(**common, gold=gold, pred=pred, explanation=result.explanation)
        rows.append(row)
        if on_row is not None:
            on_row(index, row)
    return build_report(rows, client.model, fingerprint)


def _exact_match(rows: Sequence[RowResult]) -> float:
    if not rows:
        return 0.0
    return round(sum(row.gold == row.pred for row in rows) / len(rows), 3)


def build_report(rows: Sequence[RowResult], model: str, fingerprint: str) -> EvalReport:
    accuracy: dict[str, float] = {}
    per_label: dict[str, dict[str, LabelRow]] = {}
    confusions: dict[str, list[tuple[str, str, int]]] = {}
    for field in FIELDS:
        gold = [row.gold[field] for row in rows]
        pred = [row.pred[field] for row in rows]
        accuracy[field] = round(metrics.accuracy(gold, pred), 3)
        per_label[field] = {
            label: LabelRow(
                support=stats.support,
                precision=round(stats.precision, 3),
                recall=round(stats.recall, 3),
            )
            for label, stats in metrics.label_report(gold, pred).items()
        }
        confusions[field] = metrics.top_confusions(gold, pred)

    return EvalReport(
        fingerprint=fingerprint,
        model=model,
        judge_model=None,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        examples=len(rows),
        errors=sum(row.error is not None for row in rows),
        accuracy=accuracy,
        exact_match=_exact_match(rows),
        hard_exact_match=_exact_match([row for row in rows if row.hard]),
        per_label=per_label,
        confusions=confusions,
        judge_pass_rate=None,
        rows=list(rows),
    )


def format_report(report: EvalReport) -> str:
    lines = [
        f"examples: {report.examples}   model: {report.model}   errors: {report.errors}",
        "accuracy  "
        + "   ".join(f"{field} {report.accuracy[field]:.2f}" for field in FIELDS)
        + f"   exact match {report.exact_match:.2f}"
        + f"   hard slice {report.hard_exact_match:.2f}",
    ]
    for field in FIELDS:
        labels = report.per_label[field]
        width = max([len("label"), *(len(label) for label in labels)])
        lines.append("")
        lines.append(field)
        lines.append(f"  {'label':<{width}}  {'support':>7}  {'precision':>9}  {'recall':>6}")
        for label, row in labels.items():
            lines.append(
                f"  {label:<{width}}  {row.support:>7}  {row.precision:>9.2f}  {row.recall:>6.2f}"
            )
        for gold, pred, count in report.confusions[field]:
            lines.append(f"  confused: {gold} -> {pred} ({count}x)")
    return "\n".join(lines)

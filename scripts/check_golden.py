"""Check a golden set file: valid rows, no duplicates, enough of every label.

Usage: python scripts/check_golden.py [--strict] [path]
Exit codes: 0 = OK, 1 = problems found, 2 = usage error (for example, file not found).
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import get_args

from pydantic import ValidationError

from triage.evals import GoldenExample
from triage.schemas import Topic, Urgency

MIN_ROWS = 50
MIN_PER_TOPIC = 5
MIN_PER_URGENCY = 10
MIN_HARD = 8
MAX_LISTED = 10
DEFAULT_PATH = Path("evals/golden.jsonl")


def normalize_question(question: str) -> str:
    return " ".join(question.lower().split())


def count_labels(values, allowed) -> dict:
    counts = Counter(values)
    return {label: counts[label] for label in sorted(allowed)}


def check(path: Path, *, strict: bool) -> tuple[list[GoldenExample], list[str]]:
    rows: list[GoldenExample] = []
    problems: list[str] = []
    id_lines: dict[str, list[int]] = defaultdict(list)
    question_ids: dict[str, list[str]] = defaultdict(list)

    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = GoldenExample.model_validate_json(line)
        except ValidationError as err:
            first = err.errors()[0]
            field = ".".join(str(part) for part in first["loc"]) or "(row)"
            problems.append(f"line {line_number}: {field}: {first['msg']}")
            continue
        rows.append(row)
        id_lines[row.id].append(line_number)
        question_ids[normalize_question(row.question)].append(row.id)

    for id_, line_numbers in id_lines.items():
        if len(line_numbers) > 1:
            problems.append(f"duplicate id: {id_} (lines {', '.join(map(str, line_numbers))})")
    for ids in question_ids.values():
        if len(ids) > 1:
            problems.append(f"duplicate question: {', '.join(ids)}")

    if len(rows) < MIN_ROWS:
        problems.append(f"only {len(rows)} valid rows, need at least {MIN_ROWS}")

    topic_counts = Counter(row.topic for row in rows)
    for topic in get_args(Topic):
        if topic_counts[topic] < MIN_PER_TOPIC:
            problems.append(
                f"topic {topic}: {topic_counts[topic]} rows, need at least {MIN_PER_TOPIC}"
            )

    urgency_counts = Counter(row.urgency for row in rows)
    for urgency in get_args(Urgency):
        if urgency_counts[urgency] < MIN_PER_URGENCY:
            problems.append(
                f"urgency {urgency}: {urgency_counts[urgency]} rows, "
                f"need at least {MIN_PER_URGENCY}"
            )

    hard = sum(row.hard for row in rows)
    if hard < MIN_HARD:
        problems.append(f"only {hard} hard rows, need at least {MIN_HARD}")

    if strict:
        unreviewed = [row.id for row in rows if not row.reviewed]
        if unreviewed:
            listed = ", ".join(unreviewed[:MAX_LISTED])
            more = len(unreviewed) - MAX_LISTED
            suffix = f" (and {more} more)" if more > 0 else ""
            problems.append(f"{len(unreviewed)} row(s) not reviewed: {listed}{suffix}")

    return rows, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a golden set file.")
    parser.add_argument(
        "--strict", action="store_true", help="also require every row to be reviewed"
    )
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)

    if not args.path.is_file():
        parser.error(f"{args.path} not found")

    rows, problems = check(args.path, strict=args.strict)

    hard = sum(row.hard for row in rows)
    reviewed = sum(row.reviewed for row in rows)
    print(f"rows: {len(rows)}   hard: {hard}   reviewed: {reviewed}")
    print("topic:", json.dumps(count_labels((r.topic for r in rows), get_args(Topic))))
    print("urgency:", json.dumps(count_labels((r.urgency for r in rows), get_args(Urgency))))
    print("needs_human:", json.dumps(count_labels((r.needs_human for r in rows), [False, True])))

    if not problems:
        print("OK")
        return 0
    print(f"{len(problems)} problem(s):")
    for problem in problems:
        print(f"- {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

import json

import pytest

from triage.evals import load_golden


def golden_row(id_, topic="other", urgency="low", needs_human=False, **extra):
    row = {
        "id": id_,
        "question": f"Question {id_}?",
        "topic": topic,
        "urgency": urgency,
        "needs_human": needs_human,
        "reviewed": True,
    }
    row.update(extra)
    return json.dumps(row)


@pytest.fixture
def golden(tmp_path):
    path = tmp_path / "golden.jsonl"
    rows = [
        golden_row("q1", topic="technical_issue", urgency="high", needs_human=True),
        golden_row("q2"),
        golden_row("q3", topic="grading_policy", needs_human=True, hard=True),
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_load_golden_reads_every_row(golden):
    examples = load_golden(golden)

    assert [example.id for example in examples] == ["q1", "q2", "q3"]
    assert examples[2].hard is True


def test_unreviewed_row_is_rejected_with_its_line_number(tmp_path):
    path = tmp_path / "golden.jsonl"
    path.write_text(
        golden_row("q1") + "\n" + golden_row("q2", reviewed=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=":2: q2 is not reviewed"):
        load_golden(path)

    assert len(load_golden(path, require_reviewed=False)) == 2


def test_golden_row_must_follow_the_policy(tmp_path):
    path = tmp_path / "golden.jsonl"
    path.write_text(golden_row("q1", urgency="high", needs_human=False), encoding="utf-8")

    with pytest.raises(ValueError, match="needs_human"):
        load_golden(path)


def test_duplicate_ids_are_rejected(tmp_path):
    path = tmp_path / "golden.jsonl"
    path.write_text(golden_row("q1") + "\n" + golden_row("q1") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate ids"):
        load_golden(path)

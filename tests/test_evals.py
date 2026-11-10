import json

import pytest

from triage.classifier import SYSTEM_PROMPT
from triage.evals import (
    ERROR,
    CalibrationExample,
    RowResult,
    Thresholds,
    as_label,
    build_report,
    check_judge,
    fingerprint,
    gate,
    load_golden,
    run_eval,
)
from triage.llm import FakeClient


def no_sleep(seconds):
    pass


def reply(topic, urgency, needs_human):
    return json.dumps(
        {
            "topic": topic,
            "urgency": urgency,
            "needs_human": needs_human,
            "explanation": "Fake reply for the test.",
        }
    )


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


def test_fingerprint_changes_when_prompt_or_golden_changes(golden, monkeypatch):
    before = fingerprint(golden)

    monkeypatch.setattr("triage.evals.SYSTEM_PROMPT", SYSTEM_PROMPT + " ")
    assert fingerprint(golden) != before

    monkeypatch.undo()
    assert fingerprint(golden) == before

    with golden.open("a", encoding="utf-8") as file:
        file.write(golden_row("q4") + "\n")
    assert fingerprint(golden) != before


def test_fingerprint_ignores_windows_line_endings(tmp_path):
    lf = tmp_path / "lf.jsonl"
    crlf = tmp_path / "crlf.jsonl"
    text = golden_row("q1") + "\n" + golden_row("q2") + "\n"
    lf.write_bytes(text.encode("utf-8"))
    crlf.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))

    assert fingerprint(crlf) == fingerprint(lf)


def test_run_eval_scores_predictions_and_counts_errors(golden):
    client = FakeClient(
        [
            reply("technical_issue", "high", True),
            reply("course_content", "low", False),
            "bad",
            "bad",
            "bad",
        ]
    )

    report = run_eval(load_golden(golden), client, fingerprint="test", sleep=no_sleep)

    assert report.examples == 3
    assert report.errors == 1
    assert report.accuracy["topic"] == pytest.approx(1 / 3, abs=1e-3)
    assert report.accuracy["urgency"] == pytest.approx(2 / 3, abs=1e-3)
    assert report.exact_match == pytest.approx(1 / 3, abs=1e-3)
    assert report.hard_exact_match == 0.0
    assert report.rows[2].pred["topic"] == "ERROR"
    assert report.per_label["needs_human"]["true"].recall == pytest.approx(0.5)


def verdict(grounded, consistent):
    return json.dumps({"grounded": grounded, "consistent": consistent, "reason": "Fake verdict."})


def test_run_eval_with_judge(golden):
    client = FakeClient(
        [
            reply("technical_issue", "high", True),
            reply("other", "low", False),
            reply("grading_policy", "low", True),
        ]
    )
    judge = FakeClient([verdict(True, True), verdict(False, True), "judge broke"])

    report = run_eval(
        load_golden(golden), client, fingerprint="test", sleep=no_sleep, judge_client=judge
    )

    assert [row.judge_passed for row in report.rows] == [True, False, False]
    assert report.judge_pass_rate == pytest.approx(1 / 3, abs=1e-3)
    assert report.judge_model == "fake"


def test_check_judge_reports_agreement_and_disagreements():
    common = {
        "question": "Is the lowest quiz score dropped?",
        "topic": "grading_policy",
        "urgency": "low",
        "needs_human": False,
    }
    good = CalibrationExample(**common, explanation="A policy question.", human_pass=True)
    bad = CalibrationExample(
        **common, explanation="The student is angry about a deadline.", human_pass=False
    )
    judge = FakeClient([verdict(True, True), verdict(True, True)])

    agreement, disagreements = check_judge([good, bad], judge)

    assert agreement == 0.5
    assert len(disagreements) == 1
    assert disagreements[0][0] == bad


THRESHOLDS = Thresholds(
    min_accuracy={"topic": 0.5, "urgency": 0.5, "needs_human": 0.5},
    min_recall={"needs_human:true": 0.9},
    max_errors=0,
    min_judge_pass_rate=0.5,
)


def gold_labels(example):
    return {
        field: as_label(getattr(example, field)) for field in ("topic", "urgency", "needs_human")
    }


def perfect_report(golden):
    rows = [
        RowResult(
            id=example.id,
            question=example.question,
            hard=example.hard,
            gold=gold_labels(example),
            pred=gold_labels(example),
            explanation="Right answer.",
            judge_passed=True,
            judge_reason="Fine.",
        )
        for example in load_golden(golden)
    ]
    return build_report(rows, "fake", fingerprint(golden), judge_model="fake")


def test_gate_passes_good_fresh_results(golden):
    assert gate(perfect_report(golden), THRESHOLDS, fingerprint(golden), 3) == []


def test_gate_fails_stale_results(golden):
    failures = gate(perfect_report(golden), THRESHOLDS, "0000000000000000", 3)

    assert len(failures) == 1
    assert "stale" in failures[0]


def test_gate_fails_partial_run(golden):
    failures = gate(perfect_report(golden), THRESHOLDS, fingerprint(golden), 50)

    assert failures == ["results cover 3 of 50 golden examples"]


def test_gate_fails_low_accuracy_recall_errors_and_judge(golden):
    q1, q2, q3 = load_golden(golden)
    rows = [
        RowResult(
            id=q1.id,
            question=q1.question,
            hard=q1.hard,
            gold=gold_labels(q1),
            pred={field: ERROR for field in ("topic", "urgency", "needs_human")},
            error="boom",
        ),
        RowResult(
            id=q2.id,
            question=q2.question,
            hard=q2.hard,
            gold=gold_labels(q2),
            pred={**gold_labels(q2), "topic": "course_content"},
            judge_passed=False,
        ),
        RowResult(
            id=q3.id,
            question=q3.question,
            hard=q3.hard,
            gold=gold_labels(q3),
            pred={**gold_labels(q3), "needs_human": "false"},
            judge_passed=False,
        ),
    ]
    report = build_report(rows, "fake", fingerprint(golden), judge_model="fake")

    failures = gate(report, THRESHOLDS, fingerprint(golden), 3)

    for start in ("topic accuracy", "needs_human:true recall", "1 errors > 0", "judge pass rate"):
        assert any(failure.startswith(start) for failure in failures), start

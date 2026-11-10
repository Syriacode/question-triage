import io
import json

from triage.cli import main


def run(*args):
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(list(args), stdout, stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_classify_with_fake_provider(tmp_path):
    log = str(tmp_path / "usage.jsonl")

    code, out, _ = run("--provider", "fake", "--log", log, "classify", "Is there a textbook PDF?")

    assert code == 0
    assert json.loads(out)["topic"] == "other"


def test_batch_then_stats(tmp_path):
    log = str(tmp_path / "usage.jsonl")
    questions = tmp_path / "questions.txt"
    questions.write_text("first question\n\nsecond question\n", encoding="utf-8")

    code, out, _ = run("--provider", "fake", "--log", log, "batch", str(questions))

    assert code == 0
    assert len(out.splitlines()) == 2

    code, out, _ = run("--log", log, "stats", "--price-in", "1", "--price-out", "4")

    assert code == 0
    assert json.loads(out)["calls"] == 2


def test_bad_usage_returns_2(tmp_path):
    code, _, err = run("--log", str(tmp_path / "usage.jsonl"), "explode")

    assert code == 2
    assert "invalid choice" in err


def test_eval_then_gate_with_fake_provider(tmp_path):
    log = str(tmp_path / "usage.jsonl")
    golden = tmp_path / "golden.jsonl"
    results = tmp_path / "results.json"
    thresholds = tmp_path / "thresholds.json"
    row = {
        "id": "q1",
        "question": "Is there a Discord?",
        "topic": "other",
        "urgency": "low",
        "needs_human": False,
        "reviewed": True,
    }
    golden.write_text(json.dumps(row) + "\n", encoding="utf-8")
    thresholds.write_text(json.dumps({"min_accuracy": {"topic": 0.9}}), encoding="utf-8")
    gate_args = ["--log", log, "gate", "--golden", str(golden)]
    gate_args += ["--results", str(results), "--thresholds", str(thresholds)]

    code, _, _ = run(
        "--provider",
        "fake",
        "--log",
        log,
        "eval",
        "--no-judge",
        "--golden",
        str(golden),
        "--out",
        str(results),
    )

    assert code == 0
    assert json.loads(results.read_text(encoding="utf-8"))["accuracy"]["topic"] == 1.0

    code, out, _ = run(*gate_args)

    assert code == 0
    assert "eval gate passed" in out

    golden.write_text(
        golden.read_text(encoding="utf-8").replace("Discord", "Slack"), encoding="utf-8"
    )
    code, _, err = run(*gate_args)

    assert code == 1
    assert "stale" in err

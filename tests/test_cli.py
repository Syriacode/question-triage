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

import json

import pytest

from triage.usage_log import UsageLog, cost_usd, summarize


def test_cost_is_per_million_tokens():
    assert cost_usd(1_000_000, 0, 0.5, 0.0) == pytest.approx(0.5)
    assert cost_usd(2_000, 500, 0.5, 2.0) == pytest.approx(0.002)


def test_records_are_appended_as_jsonl(tmp_path):
    path = tmp_path / "logs" / "usage.jsonl"
    log = UsageLog(path)

    log.record(model="fake", attempt=1, ok=False, error="bad reply")
    log.record(model="fake", attempt=2, ok=True, input_tokens=100, output_tokens=20)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["cost_usd"] == 0.0 for line in lines)


def test_summary_with_what_if_price(tmp_path):
    log = UsageLog(tmp_path / "usage.jsonl")
    for attempt in range(1, 5):
        log.record(
            model="fake", attempt=attempt, ok=True, input_tokens=250_000, output_tokens=50_000
        )

    summary = summarize(log.read(), price_in=1.0, price_out=4.0)

    assert summary["input_tokens"] == 1_000_000
    assert summary["cost_usd"] == pytest.approx(0.0)
    assert summary["what_if_cost_usd"] == pytest.approx(1.8)


def test_missing_log_reads_as_empty(tmp_path):
    assert UsageLog(tmp_path / "missing.jsonl").read() == []

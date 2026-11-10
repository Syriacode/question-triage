import pytest

from triage.metrics import accuracy, label_report, top_confusions

GOLD = ["a", "a", "a", "b", "b", "c"]
PRED = ["a", "a", "b", "b", "a", "ERROR"]


def test_accuracy_counts_exact_matches():
    assert accuracy(GOLD, PRED) == pytest.approx(3 / 6)


def test_accuracy_rejects_different_lengths():
    with pytest.raises(ValueError):
        accuracy(["a", "b"], ["a"])


def test_label_report_precision_and_recall():
    report = label_report(GOLD, PRED)

    assert list(report) == ["a", "b", "c"]
    a = report["a"]
    assert (a.support, a.predicted, a.correct) == (3, 3, 2)
    assert a.recall == pytest.approx(2 / 3)
    assert a.precision == pytest.approx(2 / 3)
    b = report["b"]
    assert b.recall == pytest.approx(1 / 2)
    assert b.precision == pytest.approx(1 / 2)


def test_label_never_predicted_has_zero_precision_not_a_crash():
    c = label_report(GOLD, PRED)["c"]

    assert c.predicted == 0
    assert c.precision == 0.0
    assert c.recall == 0.0


def test_predicted_labels_missing_from_gold_are_not_rows():
    assert "ERROR" not in label_report(GOLD, PRED)


def test_top_confusions_most_common_first():
    assert top_confusions(["a", "a", "b"], ["b", "b", "a"]) == [("a", "b", 2), ("b", "a", 1)]

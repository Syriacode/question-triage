from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class LabelStats:
    label: str
    support: int
    predicted: int
    correct: int

    @property
    def precision(self) -> float:
        return self.correct / self.predicted if self.predicted else 0.0

    @property
    def recall(self) -> float:
        return self.correct / self.support if self.support else 0.0


def _check_lengths(gold: Sequence[str], pred: Sequence[str]) -> None:
    if len(gold) != len(pred):
        raise ValueError(f"gold has {len(gold)} labels, pred has {len(pred)}")


def accuracy(gold: Sequence[str], pred: Sequence[str]) -> float:
    _check_lengths(gold, pred)
    if not gold:
        return 0.0
    return sum(g == p for g, p in zip(gold, pred, strict=True)) / len(gold)


def top_confusions(
    gold: Sequence[str], pred: Sequence[str], n: int = 3
) -> list[tuple[str, str, int]]:
    _check_lengths(gold, pred)
    pairs = Counter((g, p) for g, p in zip(gold, pred, strict=True) if g != p)
    return [(g, p, count) for (g, p), count in pairs.most_common(n)]


def label_report(gold: Sequence[str], pred: Sequence[str]) -> dict[str, LabelStats]:
    if len(gold) != len(pred):
        raise ValueError("gold and pred must have the same length")
    support = Counter(gold)
    predicted = Counter(pred)
    correct = Counter(g for g, p in zip(gold, pred, strict=True) if g == p)
    return {
        label: LabelStats(
            label=label,
            support=support[label],
            predicted=predicted[label],
            correct=correct[label],
        )
        for label in sorted(support)
    }

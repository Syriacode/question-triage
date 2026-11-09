import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# USD per 1M input and output tokens. Local models cost nothing to call.
PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    "qwen2.5:3b": (0.0, 0.0),
    "llama3.2:3b": (0.0, 0.0),
    "llama3.2:1b": (0.0, 0.0),
    "fake": (0.0, 0.0),
}


def cost_usd(input_tokens: int, output_tokens: int, price_in: float, price_out: float) -> float:
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


@dataclass(frozen=True)
class UsageRecord:
    timestamp: str
    model: str
    attempt: int
    ok: bool
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    error: str | None = None


class UsageLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(
        self,
        *,
        model: str,
        attempt: int,
        ok: bool,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0.0,
        error: str | None = None,
    ) -> UsageRecord:
        price_in, price_out = PRICES_PER_MILLION.get(model, (0.0, 0.0))
        rec = UsageRecord(
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            model=model,
            attempt=attempt,
            ok=ok,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(latency_ms, 1),
            cost_usd=cost_usd(input_tokens, output_tokens, price_in, price_out),
            error=error,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(rec)) + "\n")
        return rec

    def read(self) -> list[UsageRecord]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as file:
            return [UsageRecord(**json.loads(line)) for line in file if line.strip()]


def summarize(
    records: Sequence[UsageRecord], price_in: float = 0.0, price_out: float = 0.0
) -> dict[str, Any]:
    input_tokens = sum(rec.input_tokens for rec in records)
    output_tokens = sum(rec.output_tokens for rec in records)
    avg_latency = sum(rec.latency_ms for rec in records) / len(records) if records else 0.0
    return {
        "calls": len(records),
        "failed_calls": sum(not rec.ok for rec in records),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "avg_latency_ms": round(avg_latency, 1),
        "cost_usd": round(sum(rec.cost_usd for rec in records), 6),
        "what_if_cost_usd": round(cost_usd(input_tokens, output_tokens, price_in, price_out), 6),
    }

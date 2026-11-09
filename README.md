# question-triage

Classify student and support questions (topic, urgency, needs-human) with a local LLM

Part of my [learning roadmap](https://github.com/Syriacode/Mini-Blockchain/blob/main/ROADMAP.md).

| | |
|---|---|
| Language | python |
| Claude Code technique practiced | user-level ~/.claude/CLAUDE.md + /memory |

## Run it

```bash
pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

```bash
ollama pull qwen2.5:3b
python -m triage classify "..."
python -m triage batch questions.txt
python -m triage stats --price-in 1 --price-out 5
python -m triage --provider fake classify "..."  # no model needed
python -m pytest -m live -v
```

## Design decisions

- One Pydantic model drives both the JSON schema sent to the model and the validation of its reply.
- Labels are `Literal` types, so the schema has no `$ref`.
- Temperature is 0.
- There are two kinds of retry, with a hard attempt limit: backoff for call failures, and error feedback for invalid output.
- A policy rule the model can't override: high urgency always goes to a human.
- A provider-agnostic `LLMClient` Protocol, with Ollama and fake backends.
- Every attempt is logged to JSONL with tokens, latency and cost, plus what-if hosted pricing.
- Tests never call a model; real calls sit behind the `live` marker.

## Known limitations

- Accuracy is not measured yet (next project: evals).
- A 3B model mislabels some questions.
- Pydantic's lax mode accepts `"true"` as a bool.
- One question at a time, no batching or concurrency (the `batch` command runs questions in sequence).
- No caching of repeated questions.
- The prompt isn't protected against prompt injection inside a question.
- Prices are a hand-kept table.
- Local only, no hosted backend yet.

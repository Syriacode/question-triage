# question-triage

This repo is question-triage: Classify student and support questions (topic, urgency, needs-human) with a local LLM

Language: python

## How to work with me

- I'm learning, so explain each change and the reasoning behind it.
- Always run the tests after changing code, and show me the output:

```bash
pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

- Activate the venv before starting Claude Code: source .venv/Scripts/activate.
- Tests must never call a real model. Use FakeClient. Real calls go in tests marked @pytest.mark.live.
- Run python -m ruff format . after editing Python files.

## Plan

- `GUIDE.md` holds the step-by-step plan once it's added.

## Environment

- My machine runs Windows with Git Bash. Shell commands are POSIX bash.

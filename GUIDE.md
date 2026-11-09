# Week 2 Mon — Question triage CLI (step-by-step guide)

**Goal:** build a Python command-line tool that sends a student or support question to a **local LLM** and gets
back a checked, typed answer: `topic`, `urgency`, `needs_human` and a one-line `explanation`. It retries when the
model returns junk, applies one safety rule the model can't override, and logs every call's tokens, latency and
cost. Tomorrow's project measures how *accurate* it is, so today is about making it *reliable*.

**Why this project:** almost every AI-engineer job post asks for "LLM APIs, structured output, Python". This is the
smallest real app that shows all of it: messages and system prompts, a JSON schema the model must follow,
validation, retries, and cost tracking. It's also the first piece of **CourseMate**, your AI teaching assistant.

| Job requirement | Where you practice it |
|---|---|
| Python, LLM APIs, structured output | Steps 2, 3, 4 |
| Reliability: retries, timeouts, validation | Step 5 (you type the core function) |
| Cost and token awareness (LLMOps) | Steps 2, 6 |
| Provider-agnostic design (local today, hosted later) | Step 4 (`llm.py`) |
| Testable AI code without a model in CI | Steps 4, 5, 7 (fake client, live marker) |
| *Uses AI tools responsibly, with human oversight* | "You check" in every step, the `needs_human` rule |

**Claude Code technique today: user-level memory (`~/.claude/CLAUDE.md`) and `/memory`.** Until now you wrote
"how to teach me" into each repo's `CLAUDE.md`. That file belongs to *one* repo. Today you move your teaching
rules into your **personal** memory file, which Claude Code loads in **every** project on your PC, and you use
`/memory` to see exactly which memory files a session loaded.

**Time:** about 90 minutes, plus a ~2 GB model download that runs in the background during Step 1.
**Cost:** $0. The model runs on your own PC with Ollama. No API key, no credit card, nothing leaves your machine.

---

## How to use this guide with Claude Code

Every step has the same five parts:

- **Learn:** the concept, in a few sentences. Read it before prompting.
- **Prompt:** what to type into Claude Code. Use **plan mode** (`Shift+Tab` until the status bar shows
  `⏸ plan mode on`), read the plan, then approve it.
- **You check:** what *you* verify before accepting. Each check names the file and function to open.
- **Done when:** a command whose output proves the step works.
- **Commit:** the commit message to use. Ask Claude to commit, or run it yourself.

A leading `!` in the Claude Code prompt runs a shell command, as in `!python -m pytest`.

Your permission rules already allow `python -m pytest ...`, `git add` and `git commit`. Claude will ask before
`pip install`, `python -m ruff ...`, `python -m triage ...`, `curl` and `git push`. Approve those.

**One Windows rule for the whole project:** always **activate the virtual environment before you start
`claude`** (Step 0 shows how). Claude Code inherits your terminal's settings, so if the venv is active when you
type `claude`, every `python` that Claude runs is the venv's Python, with your packages installed.

---

## Step 0 — Install Ollama, start the model download, create the repo (15 min)

### 0a. Ollama and the model

**Learn.** **Ollama** is a free program that downloads open-source language models and serves them on your PC at
`http://localhost:11434`. Your code talks to it over HTTP, exactly the way it would talk to a hosted API.

**Which model and why:** your PC has 16 GB of RAM and no NVIDIA GPU, so the model runs on the CPU. Use
**`qwen2.5:3b`** (3 billion parameters, about a 2 GB download, about 3 GB of RAM while running). It's one of the
strongest models at this size and is good at following a JSON schema. On your i7, expect a few seconds per
question. If it's too slow, switch to `llama3.2:1b` (faster, less accurate). As an optional comparison later,
`llama3.2:3b`. Avoid 7B+ models today: they work, but each call takes much longer on a CPU.

**Do it.** In Git Bash:

```bash
ollama --version
```

If it says `command not found`, install it, then **close Git Bash and open a new window** (so it sees the new
program) and run `ollama --version` again:

```bash
winget install Ollama.Ollama
```

(If `winget` can't find it, download the Windows installer from ollama.com and run it.) After installing, Ollama
runs in the background; you'll see a llama icon in the system tray.

Start the download now. It takes a few minutes, so open a **second Git Bash window** for it and leave it running:

```bash
ollama pull qwen2.5:3b
```

You should see progress bars, then `success`.

### 0b. Python and the repo

Check Python (you need **3.11 or newer**):

```bash
python --version
```

If that fails or opens the Microsoft Store, try `py --version`. If `py` works, use `py -3` wherever this guide
says `python` **until the venv is active**. After that, plain `python` works.

Your `/new-project` skill has templates for Solidity, Go and TypeScript, but not Python yet, so today you create
the repo with `gh` directly and let Claude Code do the scaffolding. Go to the folder where you keep your project
repos (**not** inside another git repo), then:

```bash
gh repo create Syriacode/question-triage --public --description "Classify student and support questions (topic, urgency, needs-human) with a local LLM" --clone
cd question-triage
git branch -M main
```

Create and activate the virtual environment:

```bash
python -m venv .venv
source .venv/Scripts/activate
python --version
which python
```

**What you should see:** your prompt now starts with `(.venv)`, and `which python` prints a path ending in
`question-triage/.venv/Scripts/python`. On Windows, a venv puts its programs in `Scripts/`, not `bin/` as on
Linux and macOS. **Every time you open a new Git Bash window for this project, run
`source .venv/Scripts/activate` again.**

Save **this file** as `GUIDE.md` in the `question-triage` folder. Then start Claude Code:

```bash
claude
```

**Prompt (plan mode):**
> Scaffold this as a Python project. Use the files in ~/.claude/skills/new-project/templates/common/ as the base
> for README.md, INTERVIEW.md, CLAUDE.md and .gitattributes: replace {{NAME}} with question-triage,
> {{DESCRIPTION}} with the repo description from `gh repo view --json description --jq .description`,
> {{LANG}} with python, {{TECHNIQUE}} with "user-level ~/.claude/CLAUDE.md + /memory", and {{RUN}} with this
> bash block:
> `pip install -e ".[dev]"`, `python -m pytest`, `python -m ruff check .`, `python -m ruff format --check .`
>
> Also create:
> - pyproject.toml: setuptools build backend; project name question-triage, version 0.1.0, requires-python
>   ">=3.11", dependencies pydantic>=2.7 and httpx>=0.27; optional "dev" extra with pytest>=8 and ruff>=0.5;
>   `[tool.setuptools] packages = ["triage"]`; pytest testpaths ["tests"], a marker
>   `live: calls a real local Ollama model (run with: pytest -m live)` and `addopts = "-m 'not live'"`;
>   ruff line-length 100 and lint rules E, F, I, UP, B.
> - triage/__init__.py with only the docstring `"""Question triage: classify questions with an LLM."""`
> - tests/test_smoke.py with one test that imports triage and asserts triage.__doc__ is truthy
> - .gitignore: .venv/, __pycache__/, *.egg-info/, .pytest_cache/, .ruff_cache/, logs/, .env
> - .github/workflows/ci.yml with `permissions: {}` at the top and `contents: read` on the job (same style as my
>   Go template in ~/.claude/skills/new-project/templates/go/ci.yml), using actions/checkout@v5 with
>   persist-credentials: false and actions/setup-python@v6 with Python "3.12". Steps: `pip install -e ".[dev]"`,
>   `ruff check .`, `ruff format --check .`, `python -m pytest -v`.
>
> Then run `pip install -e ".[dev]"`, `python -m pytest`, `python -m ruff check .` and
> `python -m ruff format --check .` and show me the output.

Claude will ask to read files in `~/.claude/skills/...` because they're outside the project. Approve it.

**You check:**
- `pyproject.toml`, `[project.optional-dependencies]`: `dev` contains pytest and ruff. Ask: *"What does
  `pip install -e .` do differently from `pip install .`, and what do the `[dev]` brackets mean?"*
  (Short answer: `-e` is "editable": Python imports your code straight from this folder, so edits take effect
  without reinstalling. `[dev]` adds the optional extras.)
- `pyproject.toml`, `[tool.pytest.ini_options]`: `addopts` contains `-m 'not live'`. That's what keeps real
  model calls out of normal test runs and CI.
- `.gitignore` contains `.venv/` and `.env`. Run `!git status` and make sure `.venv` is **not** listed.

**Done when:** `python -m pytest` prints `1 passed`, and both ruff commands print `All checks passed!` and
`... already formatted` (or "files left unchanged").

**Commit:** `Scaffold Python project` (include GUIDE.md). Then push and check CI:

```text
!git push -u origin main
!gh run list --branch main --limit 1
```

Re-run the second command every few seconds until it shows `completed` and `success`.

---

## Step 1 — Your personal teaching rules: `~/.claude/CLAUDE.md` and `/memory` (10 min)

**Learn (Claude Code).** Claude Code loads several memory files at the start of a session, and **adds them
together**:

| File | Applies to | In git? |
|---|---|---|
| `~/.claude/CLAUDE.md` (your **user** memory) | every project on this PC | no, it lives in your home folder |
| `CLAUDE.md` in the repo (**project** memory) | this repo, for anyone who clones it | yes |
| `CLAUDE.local.md` in the repo | this repo, only you | no (git-ignored) |

When two say different things, the more specific one (project) wins. Rule of thumb: **who you are and how you
learn** goes in user memory; **how this repo works** (commands, layout, rules) goes in project memory. On
Windows, `~/.claude/CLAUDE.md` is `C:\Users\<you>\.claude\CLAUDE.md`.

`/memory` (typed inside Claude Code) lists every memory file the current session loaded and opens the one you
pick in your editor. It's the quickest way to answer "why is Claude doing that?". It may also show an
**auto-memory** setting: those are notes Claude writes for itself. Today you write the instructions yourself.

**Do it.** Quit Claude Code (`/exit`). In Git Bash, this **adds** to the file (it creates it if it's missing, and
keeps anything already there):

```bash
mkdir -p ~/.claude
cat >> ~/.claude/CLAUDE.md <<'EOF'

## How to teach me (all projects)
- I teach undergrad CS and grad blockchain. I know Python basics, Go and Solidity. I'm rusty on modern Python
  (type hints, Pydantic, packaging) and new to AI engineering.
- When you use a Python feature or AI idea for the first time in a session, explain it in one or two sentences,
  comparing it to something I already know when that helps.
- For AI ideas (tokens, temperature, structured output, evals, RAG, agents), also say what can go wrong and how
  I would test it.
- When I ask for a hint, give one hint only. Don't write the solution.
- When I ask for a review, first ask me what I expect the code to do.
- Never edit a test to make it pass. If a test looks wrong, tell me and stop.
- Never read or print .env files or secrets.
EOF
cat ~/.claude/CLAUDE.md
```

The `<<'EOF' ... EOF` is a *here-document*: everything between the two `EOF` lines is fed to `cat`, and `>>`
appends it to the file.

Now start Claude Code again (venv still active):

```bash
claude
```

Type:

```text
/memory
```

**What you should see:** a list that includes **User memory** (`~/.claude/CLAUDE.md`) and **Project memory**
(`./CLAUDE.md`). Pick User memory: your editor opens the file you just wrote. Close it without changes. Press
`Esc` to leave the menu.

**Prove it applies everywhere.** Quit (`/exit`), then start Claude Code in a folder that has nothing to do with
this project:

```bash
cd ~
claude
```

**Prompt:**
> Without reading any files, tell me which memory files you loaded in this session, and quote the rule about
> hints.

It should quote your "one hint only" rule, even though your home folder isn't a project. Quit and go back:

```bash
cd -
claude
```

(`cd -` returns to the previous folder. If Git Bash prints the path, you're back in `question-triage`.)

**Clean up the project file.** **Prompt (no plan mode needed):**
> In @CLAUDE.md, under "How to work with me", add these project rules, word for word:
> - Activate the venv before starting Claude Code: `source .venv/Scripts/activate`.
> - Tests must never call a real model. Use FakeClient. Real calls go in tests marked `@pytest.mark.live`.
> - Run `python -m ruff format .` after editing Python files.
>
> Don't copy my teaching rules here; they live in my user memory.

**You check:** open `CLAUDE.md`: it has project facts only. Open `~/.claude/CLAUDE.md` (or `/memory`): it has
teaching rules only. Ask Claude: *"If my user memory says 'explain every change' and this project's CLAUDE.md
said 'don't explain, just code', which would you follow, and why?"*

**Done when:** `git diff --stat` shows only `CLAUDE.md` changed. (Your user memory isn't in this repo, so git
doesn't see it. That's the point.)

**Commit:** `Add project rules to CLAUDE.md`

By now `ollama pull` in your second window should say `success`. Check with `ollama list`: it shows
`qwen2.5:3b`.

---

## Step 2 — Talk to the model by hand (10 min)

**Learn (AI).** Before writing code, see the raw API. A chat request is a list of **messages**, each with a
`role`:

- `system`: instructions the model should follow for the whole conversation ("you triage questions...").
- `user`: the input ("my portal is down...").
- `assistant`: the model's earlier replies (you'll send these back in Step 5 when you retry).

The model reads and writes **tokens**, chunks of text of about 3–4 characters of English each. Ollama reports
`prompt_eval_count` (input tokens) and `eval_count` (output tokens). Hosted APIs charge **per million tokens**,
with output usually priced several times higher than input, so these two numbers *are* your cost.

**Temperature** controls randomness. At `0` the model picks its most likely token every time, so the same input
gives (almost always) the same output. That's what you want for classification. Higher values are for creative
writing.

**Prompt:**
> Run this curl command and show me the raw output, then pretty-print it with `python -m json.tool`. Explain
> each top-level field, especially message.content, prompt_eval_count, eval_count and total_duration (and its
> unit). Don't write any files.
>
> `curl -s http://localhost:11434/api/chat -d '{"model":"qwen2.5:3b","stream":false,"options":{"temperature":0},"messages":[{"role":"system","content":"You label help-desk questions. Reply with exactly one word: urgent or not_urgent."},{"role":"user","content":"The submission site is down and my project is due in one hour."}]}'`

The first call takes longer: Ollama is loading the model into RAM. Run it again and it's faster.

**What you should see:** `"content":"urgent"` (or close to it), `prompt_eval_count` around 40–60,
`eval_count` a small number, and `total_duration` in **nanoseconds**.

**Temperature experiment. Prompt:**
> Run the same request 3 times with this system prompt instead: "Write a creative 6-word title for a lecture on
> hashing." First with temperature 0, then 3 times with temperature 1.2. Show only message.content for each run.

Predict first: which set will vary? At `0` the three titles should match; at `1.2` they differ.

**Structured output. Prompt:**
> Run the first request again, but replace the system message with "You label help-desk questions." and add
> `"format":{"type":"object","properties":{"urgency":{"type":"string","enum":["low","medium","high"]}},"required":["urgency"]}`
> to the JSON body. Show message.content. Then explain how Ollama makes the model follow that schema.

**What you should see:** `message.content` is a JSON string like `{"urgency": "high"}`. Ollama uses
**constrained decoding**: while generating, it only allows tokens that keep the output valid against your schema.

**You check:** in your own words, answer: *"If the schema guarantees the shape, why will my code still validate
the reply with Pydantic?"* (Answers: another provider may not enforce schemas the same way; some rules, like
`max_length` or a policy, aren't enforced by decoding; and the model can still be cut off mid-reply. Never trust
input you didn't check, even from your own model.)

**Done when:** you've seen a JSON reply that matches the schema, and you can say what `prompt_eval_count` and
`eval_count` mean.

**Commit:** nothing. No files changed.

---

## Step 3 — The schema: what a triage result must look like (10 min)

**Learn (Python).**
- **Pydantic** turns a class with type hints into a validator. `Triage.model_validate_json(text)` parses JSON
  and checks every field, raising `ValidationError` with a list of what's wrong. It's like a Solidity `struct`
  plus all the `require` checks, generated from the types.
- `Literal["low", "medium", "high"]` means "exactly one of these strings". Pydantic turns it into a JSON schema
  `enum`, which is what you sent to Ollama in Step 2.
- `ConfigDict(extra="forbid")` rejects fields you didn't define. Without it, a model that invents a
  `"confidence"` field would pass silently.
- `Triage.model_json_schema()` produces the JSON schema you'll send to the model. **One definition drives both
  the prompt constraint and the validation**, so they can't drift apart.

**Prompt (plan mode):**
> Create triage/schemas.py with:
> - `Topic = Literal["course_content", "assignment_help", "deadlines_extensions", "grading_policy",
>   "technical_issue", "account_access", "other"]`
> - `Urgency = Literal["low", "medium", "high"]`
> - a Pydantic model `Triage` with `model_config = ConfigDict(extra="forbid")` and fields: topic: Topic,
>   urgency: Urgency, needs_human: bool, explanation: str with Field(min_length=1, max_length=300).
>   Use Literal, not Enum classes, so the JSON schema has no $ref.
>
> Create tests/test_schemas.py:
> 1. test_valid_json_parses: a valid JSON string parses and the fields are right
> 2. test_bad_output_is_rejected, parametrized over: topic "homework", urgency "urgent", needs_human "maybe",
>    explanation "", and an extra field "confidence": 0.9. Each raises ValidationError.
> 3. test_missing_field_is_rejected: no urgency raises ValidationError
> 4. test_schema_lists_labels_inline: the schema JSON has no "$ref", urgency's enum is ["low", "medium", "high"],
>    and additionalProperties is False
>
> Delete tests/test_smoke.py. Run ruff format, ruff check and pytest. Then print
> `Triage.model_json_schema()` as JSON so I can compare it with the schema I sent with curl.

**You check:**
- `triage/schemas.py`, class `Triage`: four fields, `extra="forbid"`, no `Enum` classes.
- The printed schema has `"enum": [...]` lists, `"required"` with all four fields, and
  `"additionalProperties": false`. It's the same idea as your hand-written curl schema, just complete.
- `tests/test_schemas.py`, `test_bad_output_is_rejected`: 5 cases. Ask: *"Why does `needs_human: "maybe"` fail
  but `needs_human: "true"` might pass? What is Pydantic's 'lax mode'?"* Keep the answer for Known limitations.

**Done when:** `python -m pytest -v` shows 8 tests passing (the parametrized one counts as 5).

**Commit:** `Add Triage schema with validation tests`

---

## Step 4 — `llm.py`: one interface, two backends (15 min)

**Learn (design).** Your app shouldn't care which model it talks to. So `llm.py` defines **one small interface**
and the rest of the code only uses that:

- `LLMClient` is a `typing.Protocol`: any class with a `model` attribute and a matching `chat(...)` method fits,
  with no inheritance needed. It's the same idea as your Go `ChainReader` interface: implicit, defined where it's
  used.
- `OllamaClient` is the real backend: one `POST /api/chat` with `httpx`.
- `FakeClient` returns replies you script in advance. Tests use it, so they run in milliseconds with no model,
  in CI too.
- `LLMResponse` is what every backend returns: text, model, input and output tokens, latency.

**Interview angle: local vs hosted.** Switching to a hosted API later means writing one more class (for example
`HostedClient`) that fits `LLMClient` and choosing it with `--provider`. What changes: an API key read from
`.env`, a different URL and request shape (hosted APIs call the schema option something like `response_format`
or use tool definitions), different names for the token counts in the response, real per-token prices, and
**rate limits** (HTTP 429), which you must retry with backoff. What doesn't change: the schema, the classifier,
the tests.

**Prompt 1 (plan mode):**
> Create triage/llm.py with:
> - `class Message(TypedDict)`: role (Literal "system", "user", "assistant") and content (str)
> - `@dataclass(frozen=True) class LLMResponse`: text: str, model: str, input_tokens: int, output_tokens: int,
>   latency_ms: float
> - `class LLMError(Exception)` with the docstring "The model could not be reached or returned an error."
> - `class LLMClient(Protocol)`: attribute `model: str` and method
>   `chat(self, messages: Sequence[Message], *, schema: dict[str, Any] | None = None, temperature: float = 0.0) -> LLMResponse`
> - `class OllamaClient`: `__init__(self, model, base_url="http://localhost:11434", timeout=120.0, http: httpx.Client | None = None)`;
>   store `self.model` and `self._http = http or httpx.Client(base_url=base_url, timeout=timeout)`.
>   `chat` POSTs to /api/chat with body {model, messages, stream: False, options: {temperature}}, plus "format": schema
>   only when schema is not None. Time the call with time.perf_counter. Call raise_for_status. Catch
>   httpx.HTTPError and raise LLMError("ollama request failed: ...") from it. Return LLMResponse with text from
>   message.content, model from the reply (default self.model), input_tokens from prompt_eval_count and
>   output_tokens from eval_count, both with .get(..., 0).
> - `class FakeClient`: `__init__(self, replies: Sequence[str | Exception] | None = None)`, model = "fake",
>   `self.calls: list[list[Message]]` records every messages list it receives. If replies is None, always return
>   DEFAULT_REPLY = a valid Triage JSON with topic "other", urgency "low", needs_human false, explanation
>   "Fake provider: no model was called.". Otherwise pop replies in order: an Exception is raised, a str is
>   returned as text with input_tokens=100, output_tokens=20, latency_ms=1.0. Running out of replies raises
>   AssertionError.
> - `make_client(provider: str, model: str, base_url: str) -> LLMClient`: "ollama" → OllamaClient, "fake" →
>   FakeClient(), anything else → ValueError.

**Prompt 2 (plan mode):**
> Create tests/test_llm.py that tests OllamaClient with `httpx.MockTransport`, so no real server is needed. Build
> the client with `httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))`.
> 1. test_sends_schema_and_temperature_and_reads_token_counts: the handler records the request and returns
>    {"model": "qwen2.5:3b", "message": {"role": "assistant", "content": "{\"topic\": \"other\"}"}, "done": true,
>    "prompt_eval_count": 312, "eval_count": 41}. Check the path is /api/chat, stream is False, format equals
>    the schema passed in, options equals {"temperature": 0.0}, and the response has text and tokens (312, 41).
> 2. test_server_error_becomes_llm_error: handler returns 500 → LLMError
> 3. test_connection_error_becomes_llm_error: handler raises httpx.ConnectError → LLMError
>
> Run ruff format, ruff check and pytest.

**You check:**
- `triage/llm.py`, `OllamaClient.chat`: the body has `"stream": False` (otherwise Ollama sends the reply in many
  small pieces), and `format` is added only when there's a schema.
- `triage/llm.py`, `OllamaClient.chat`: every `httpx` error becomes `LLMError`. Ask: *"Why should the classifier
  only ever see LLMError, never an httpx exception?"* (So swapping providers doesn't change error handling.)
- `triage/llm.py`, `OllamaClient.__init__`: the `http` parameter. Ask: *"How is passing in the HTTP client
  'dependency injection', and what did it let my test do?"*
- `tests/test_llm.py`: no test talks to `localhost:11434`.

**Done when:** `python -m pytest -v` shows 11 tests passing.

**Commit:** `Add provider-agnostic LLM client with Ollama and fake backends`

---

## Step 5 — Type `classify` yourself: validate, retry, enforce policy (20 min)

**Learn (AI reliability).** A model call can fail in two different ways, and they need different retries:

1. **The call fails** (Ollama isn't running, timeout, HTTP 500): wait and try again, waiting longer each time
   (**exponential backoff**: 1 s, then 2 s, ...), because the problem is usually temporary.
2. **The call works but the reply is invalid** (bad JSON, unknown label): waiting won't help. Instead, send the
   bad reply back as an `assistant` message plus a `user` message saying exactly what was wrong, and ask again.
   Models are good at fixing their output when you show them the error.

Either way, **stop after a few attempts** (3 here) and raise a clear error. An infinite retry loop is how a bug
turns into a big bill on a hosted API.

Finally, a **policy** is a rule your code enforces *after* the model answers, because some decisions shouldn't be
left to a 3B model: if `urgency` is `high`, `needs_human` is always `True`.

**Prompt 1 (plan mode):**
> Create triage/classifier.py with these parts only. Do NOT write `classify`; leave a stub that raises
> NotImplementedError, because I'll type it myself.
> - SYSTEM_PROMPT: says it triages questions sent to a university course's help inbox, from students or people
>   using the course website, and replies with JSON only matching the given schema. Define each label:
>   topic: course_content (explaining lecture or reading material), assignment_help (how to approach or fix
>   their homework or project), deadlines_extensions (due dates, late work, extension requests),
>   grading_policy (how work is graded, regrade requests, grade disputes), technical_issue (course website,
>   submission system or software is broken), account_access (login, password, enrollment, permissions),
>   other. urgency: high if it blocks the student right now, a deadline is within 24 hours, or it mentions a
>   health, safety or personal emergency; medium if it needs an answer within a few days; low otherwise.
>   needs_human: true if the answer needs a decision only staff can make (extensions, regrades, exceptions,
>   account changes) or the person seems upset or in distress; false if a standard answer or pointer to course
>   materials would do. explanation: one short sentence saying why.
> - `class TriageError(Exception)` with `__init__(self, attempts: int, last_error: str)`, message
>   "no valid triage after {attempts} attempts: {last_error}", and both values stored as attributes.
> - `build_messages(question: str) -> list[Message]`: a system message with SYSTEM_PROMPT and a user message
>   "Question:\n{question}".
> - `describe_errors(err: ValidationError) -> str`: for each error in err.errors(include_url=False), make
>   "field: msg" (join loc with "."; use "reply" when loc is empty), joined with "; ".
> - `apply_policy(result: Triage) -> Triage`: if urgency is "high" and needs_human is False, return
>   `result.model_copy(update={"needs_human": True})`; otherwise return result unchanged.
> - the stub: `def classify(question: str, client: LLMClient, *, log: UsageLog | None = None, max_attempts: int = 3, temperature: float = 0.0, sleep: Callable[[float], None] = time.sleep) -> Triage`
>
> UsageLog doesn't exist yet: create triage/usage_log.py with just `class UsageLog: pass` for now.
>
> Then create tests/test_classifier.py using FakeClient and a `no_sleep` function that does nothing:
> 1. test_valid_first_reply_is_returned: one good reply → right topic, exactly 1 call, first message is system
> 2. test_invalid_reply_is_retried_with_the_error: replies "not json at all" then a good one → 2 calls; in the
>    second call, the second-last message is {"role": "assistant", "content": "not json at all"} and the last
>    message's content contains "did not match the schema"
> 3. test_gives_up_after_max_attempts: three replies with topic "homework" → TriageError with attempts == 3, and
>    exactly 3 calls
> 4. test_network_error_backs_off_then_succeeds: LLMError("connection refused") then a good reply; pass
>    `sleep=waits.append` → waits == [1]
> 5. test_high_urgency_always_needs_a_human: model says urgency high, needs_human false → result has True
>
> Run pytest and show me the failures.

**What you should see:** `5 failed, 11 passed`. All 5 new tests fail with `NotImplementedError` (even test 3:
`pytest.raises(TriageError)` only catches a `TriageError`, so any other exception still fails the test). The 11
earlier tests still pass.

**Now type `classify` yourself.** Don't ask Claude to write it. In your editor, replace the stub in
`triage/classifier.py` with this skeleton and fill in the `# ...` parts:

```python
def classify(
    question: str,
    client: LLMClient,
    *,
    log: UsageLog | None = None,
    max_attempts: int = 3,
    temperature: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Triage:
    messages = build_messages(question)
    schema = Triage.model_json_schema()
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        # 1. Call the model. If it raises LLMError:
        #    save str(err) in last_error, sleep 2 ** (attempt - 1) seconds
        #    (but not after the last attempt), and `continue`.

        # 2. Validate: result = Triage.model_validate_json(response.text)
        #    If it raises ValidationError:
        #    last_error = f"invalid output: {describe_errors(err)}"
        #    messages = [*messages, <assistant message with response.text>,
        #                <user message: "That reply did not match the schema: "
        #                 f"{last_error}. Reply again with JSON only.">]
        #    and `continue`.

        # 3. Success: return apply_policy(result)

    raise TriageError(max_attempts, last_error)
```

Ignore `log` for now; you'll add logging in Step 6. Run:

```text
!python -m pytest tests/test_classifier.py -v
```

Python hints, if you need them:
- `try: ... except LLMError as err: ...` is Python's version of Go's `if err != nil`.
- `[*messages, a, b]` builds a **new** list: the old items, then `a` and `b`. Why a new list instead of
  `messages.append(...)`? Because `FakeClient.calls` keeps a reference to each list it was given, and appending
  would change what the test sees for the *earlier* call.

If you get stuck, ask for **one hint**:
> Give me one hint for the first failing test in tests/test_classifier.py. Don't write the code.

**Once all 5 pass, get a review:**
> Review `classify` in @triage/classifier.py. Before telling me anything, ask me (1) why the
> ValidationError branch doesn't sleep, and (2) what would happen to a hosted-API bill if max_attempts were
> missing and the model kept returning a bad label. Then tell me one thing a senior Python reviewer would change.
> Don't edit the file.

**You check:**
- `triage/classifier.py`, `classify`: the `sleep` happens only in the `LLMError` branch and is skipped on the
  last attempt.
- `triage/classifier.py`, `classify`: on a `ValidationError`, the bad reply goes back as role `assistant`,
  the correction as role `user`.
- `triage/classifier.py`, `classify`: the success path returns `apply_policy(result)`, not `result`.
- `tests/test_classifier.py`, `test_network_error_backs_off_then_succeeds`: ask *"Why does `classify` take a
  `sleep` parameter instead of calling `time.sleep` directly?"* (Same reason `OllamaClient` takes `http`.)
- Run `!python -m ruff format .` and `!python -m ruff check .`.

**Done when:** `python -m pytest -v` shows 16 tests passing.

**Commit:** `Add classify with validation retries, backoff and policy`

Commit **now**, before the experiment below.

**Break it on purpose (5 min).** Predict first: which test fails?

**Prompt (no plan mode needed):**
> Break @triage/classifier.py on purpose: change the last line of the success path in classify from
> `return apply_policy(result)` to `return result`. Don't touch any test. Run pytest and explain the result.

**What you should see:** exactly one failure, `test_high_urgency_always_needs_a_human`. Without that test, a
model mistake on a "portal down, due in 1 hour" question would quietly skip the human. Undo it:

```text
!git restore triage/classifier.py
!git status
!python -m pytest
```

**Done when:** `git status` says `nothing to commit, working tree clean` and pytest shows 16 passed.

**Commit:** nothing for the experiment.

---

## Step 6 — Token and cost log, then the command line (15 min)

**Learn (LLMOps).** You can't control what you don't measure. Every model call (including failed retries)
appends one line of JSON to `logs/usage.jsonl`: time, model, attempt number, ok or not, input and output tokens,
latency, cost. One JSON object per line (**JSONL**) is the standard format for logs: easy to append, easy to load
into pandas later.

Your local model costs $0 per call, so the log also lets you ask **"what would this cost on a hosted API?"**:
`stats --price-in X --price-out Y` multiplies your real token counts by any price per million tokens. When you
compare providers, take X and Y from their current pricing pages; the numbers in this guide are only examples.

**Prompt 1 (plan mode):**
> Replace triage/usage_log.py with:
> - `PRICES_PER_MILLION: dict[str, tuple[float, float]]` (USD per 1M input and output tokens) with
>   qwen2.5:3b, llama3.2:3b, llama3.2:1b and fake all at (0.0, 0.0), and a comment that local models cost nothing
>   to call.
> - `cost_usd(input_tokens, output_tokens, price_in, price_out) -> float`: tokens times price, divided by 1,000,000
> - `@dataclass(frozen=True) class UsageRecord`: timestamp: str, model: str, attempt: int, ok: bool,
>   input_tokens: int, output_tokens: int, latency_ms: float, cost_usd: float, error: str | None = None
> - `class UsageLog` with `__init__(self, path: Path)`, `record(self, *, model, attempt, ok, input_tokens=0,
>   output_tokens=0, latency_ms=0.0, error=None) -> UsageRecord` that looks up the price (default (0.0, 0.0)),
>   uses `datetime.now(UTC).isoformat(timespec="seconds")`, rounds latency to 1 decimal, creates the parent
>   folder, and appends `json.dumps(asdict(rec))` plus a newline, opening the file with encoding="utf-8"; and
>   `read(self) -> list[UsageRecord]` that returns [] if the file doesn't exist and skips blank lines.
> - `summarize(records, price_in=0.0, price_out=0.0) -> dict` with keys calls, failed_calls, input_tokens,
>   output_tokens, avg_latency_ms (0.0 when empty, rounded to 1 decimal), cost_usd and what_if_cost_usd (both
>   rounded to 6 decimals).
>
> Then in @triage/classifier.py, inside classify (don't restructure my code), add `if log:` calls to
> log.record: in the LLMError branch (ok=False, error=last_error), in the ValidationError branch (ok=False,
> tokens and latency from the response, error=last_error), and on success (ok=True, tokens and latency). Use
> response.model for the model when there's a response, client.model otherwise.
>
> Tests: tests/test_usage_log.py with test_cost_is_per_million_tokens (1,000,000 input at 0.5 → 0.5; 2,000 input
> and 500 output at 0.5/2.0 → 0.002), test_records_are_appended_as_jsonl (two records → two lines, cost 0.0),
> test_summary_with_what_if_price (4 records of 250,000 in / 50,000 out at 1.0/4.0 → 1,000,000 input tokens,
> cost_usd 0.0, what_if_cost_usd 1.8), test_missing_log_reads_as_empty. Use tmp_path and pytest.approx. And add
> test_every_attempt_is_logged to tests/test_classifier.py: replies "oops" then a good one → records are
> [(1, False), (2, True)] and the second has input_tokens 100.
> Run ruff format, ruff check and pytest.

**Prompt 2 (plan mode):**
> Create triage/cli.py and triage/__main__.py.
> - `build_parser()` with argparse, prog "triage". Global options: --provider (choices ollama, fake; default env
>   TRIAGE_PROVIDER or "ollama"), --model (default env TRIAGE_MODEL or "qwen2.5:3b"), --ollama-url (default env
>   OLLAMA_URL or "http://localhost:11434"), --log (Path, default logs/usage.jsonl). Required subcommands:
>   `classify QUESTION`, `batch FILE` (Path), `stats` with --price-in and --price-out (float, default 0.0, help
>   "what-if price, USD per 1M input/output tokens").
> - `main(argv: list[str], stdout: TextIO, stderr: TextIO) -> int`, like run() in my Go chain reader. Parse inside
>   `contextlib.redirect_stderr(stderr)` and `redirect_stdout(stdout)`, catch SystemExit and return its code (so bad
>   usage returns 2). stats: print summarize(...) as indented JSON, return 0, and don't create a client.
>   classify: print `result.model_dump_json(indent=2)`; on TriageError print "error: ..." to stderr and return 1.
>   batch: for each non-blank line, print one JSON line {"question": ..., **result.model_dump()} or
>   {"question": ..., "error": "..."}; keep going after an error; return 1 if any failed, else 0.
> - triage/__main__.py: `sys.exit(main(sys.argv[1:], sys.stdout, sys.stderr))`
>
> tests/test_cli.py with a helper run(*args) using io.StringIO:
> 1. test_classify_with_fake_provider: exit 0 and the JSON topic is "other"
> 2. test_batch_then_stats: a file with "first question", a blank line, "second question" → 2 output lines; then
>    stats with --price-in 1 --price-out 4 shows calls == 2
> 3. test_bad_usage_returns_2: `explode` → 2, and stderr contains "invalid choice"
> Use tmp_path for every --log. Add a CI step "Smoke test the CLI" after the tests:
> `python -m triage --provider fake classify "Is there a textbook PDF?"`. Run ruff format, ruff check and pytest.

**You check:**
- `triage/usage_log.py`, `UsageLog.record`: the file is opened with `"a"` (append), not `"w"`. Ask: *"What would
  `"w"` do to yesterday's log?"*
- `triage/classifier.py`, `classify`: a failed attempt is logged **with its tokens**. Ask: *"Why do failed
  retries count toward cost?"*
- `triage/cli.py`, `main`: it never calls `sys.exit` itself; only `__main__.py` does. That's what lets
  `tests/test_cli.py` call `main` directly.
- `.gitignore` has `logs/`, so your usage log never gets committed.

**Done when:** `python -m pytest -v` shows **24 passed** (no live tests exist yet, so nothing is deselected),
and:

```text
!python -m triage --provider fake classify "Is there a textbook PDF?"
```

prints a JSON object with `"explanation": "Fake provider: no model was called."`

**Commit:** `Add usage log and CLI`

---

## Step 7 — Run it for real on your PC (10 min)

**Learn.** Unit tests prove your code does what *you* believe. Now check what the *model* does. Real-model tests
are slow and not 100% repeatable, so they get the `live` marker and stay out of CI.

Make sure Ollama is running (`ollama list` works) and the venv is active. These run the real model, so expect a
few seconds per question (the very first call also loads the model).

**One question:**

```text
!python -m triage classify "I can't log in to the course site since the password reset."
```

**What you should see:** JSON with `"topic": "account_access"`, an urgency, `needs_human` and a one-line
explanation.

**A batch.** **Prompt (no plan mode needed):**
> Create questions.txt with these 7 lines, exactly:
> How do I compute a SHA-256 hash in Python for the lab?
> My submission portal says "403 forbidden" and the assignment is due in 2 hours.
> Can I get a 3-day extension on project 2? I had a family emergency.
> Why did I lose 10 points on question 4? I think the rubric was applied wrong.
> What does "proof of work" mean in the week 3 slides?
> I can't log in to the course site since the password reset.
> Is there a textbook PDF for this class?
>
> Then run `python -m triage batch questions.txt` and show me the results as a table: question, topic, urgency,
> needs_human.

**You check (this is the important part):** go through the table **yourself** and mark each row right or wrong.
You know these labels better than the model does. My expectation: the 403 one is `technical_issue`, `high`,
`needs_human: true` (by your policy); the extension and the regrade are `needs_human: true`. A 3B model will
probably get one or two wrong. Write down which ones: tomorrow you'll turn this into a proper golden set and
**measure** accuracy instead of eyeballing it.

**Cost and tokens:**

```text
!python -m triage stats
!python -m triage stats --price-in 1 --price-out 5
```

**What you should see:** `calls` is 8 or more (more if any retries happened), `input_tokens` is several hundred per
call (the system prompt plus the schema dominate), `cost_usd` is `0.0`, and `what_if_cost_usd` is a fraction of a
cent. Ask Claude: *"Using these numbers, what would 10,000 questions a day cost per month at these example
prices, and which part of the prompt would I shrink first?"* Keep the answer for Interview Q3.

**Retries in the log.** Open `logs/usage.jsonl` in your editor. If any line has `"ok": false`, read its
`error`: that's a real model mistake your retry caught. If every line is `ok`, that's constrained decoding at
work. To see a *network* retry, stop Ollama (right-click the tray icon → Quit Ollama) and run:

```text
!python -m triage classify "test"
```

It waits about 3 seconds (1 s + 2 s backoff), then prints `error: no valid triage after 3 attempts: ollama
request failed: ...` and exits with 1. Start Ollama again from the Start menu.

**Live tests. Prompt (plan mode):**
> Create tests/test_live.py with `pytestmark = pytest.mark.live`, and a module-scoped fixture that GETs
> http://localhost:11434/api/version with a 2 second timeout and calls pytest.skip("Ollama is not running on
> localhost:11434") if that fails, otherwise returns OllamaClient(model="qwen2.5:3b"). Tests:
> test_obvious_login_problem ("I can't log in to the course website since I reset my password." →
> account_access) and test_extension_request_needs_a_human ("Can I get a 3-day extension on project 2? I was
> sick." → needs_human True). Run `python -m pytest -m live -v`, then plain `python -m pytest`.

**What you should see:** `python -m pytest -m live -v` runs 2 tests against the real model. Plain
`python -m pytest` shows `24 passed, 2 deselected`: the live tests are skipped by default. If a live test fails,
**don't change the test to make it pass**. Note which one; it's evidence for tomorrow's evals.

**Done when:** you've marked every batch row right or wrong, and `python -m pytest` shows `24 passed, 2
deselected`.

**Commit:** `Add sample questions and live model tests`

---

## Step 8 — README, INTERVIEW.md, push, green CI (10 min)

**Prompt 1 (README):**
> In @README.md, add to "Run it": `ollama pull qwen2.5:3b`, `python -m triage classify "..."`,
> `python -m triage batch questions.txt`, `python -m triage stats --price-in 1 --price-out 5`,
> `python -m triage --provider fake classify "..."` (no model needed), and `python -m pytest -m live -v`.
> Replace the "Design decisions" TODO with short bullets on: one Pydantic model drives both the JSON schema sent
> to the model and the validation; Literal labels so the schema has no $ref; temperature 0; two retry kinds
> (backoff for call failures, error feedback for invalid output) and a hard attempt limit; a policy rule the
> model can't override (high urgency → human); a provider-agnostic LLMClient Protocol with Ollama and fake
> backends; every attempt logged to JSONL with tokens, latency and cost, plus what-if hosted pricing; tests that
> never call a model, with real calls behind the `live` marker.
> Replace the "Known limitations" TODO with: accuracy is not measured yet (next project: evals); a 3B model
> mislabels some questions; Pydantic's lax mode accepts "true" as a bool; one question at a time, no batching or
> concurrency; no caching of repeated questions; the prompt isn't protected against prompt injection inside a
> question; prices are a hand-kept table; local only, no hosted backend yet.
> Don't touch the "How I used Claude Code" section.

**Prompt 2 (INTERVIEW.md):**
> Fill in @INTERVIEW.md with these 5 questions and short model answers (5–8 sentences each), based on this code:
> 1. Walk me through what happens when I run `triage classify "..."`: the messages, the system prompt, the
>    schema, constrained decoding, Pydantic validation, retries, the policy and the usage log.
> 2. The model is already constrained by a JSON schema. Why validate again with Pydantic, and what can still go
>    wrong even when the JSON is valid?
> 3. What are tokens, why are input and output priced differently, and how would you estimate the monthly cost
>    of 10,000 questions a day? Use the numbers from my `triage stats` output. Why temperature 0 here?
> 4. Which errors should you retry and how? Cover backoff, rate limits (429), errors you should NOT retry,
>    feeding validation errors back, attempt limits, and logging failed attempts.
> 5. LLM system design: design a triage service for a university help inbox with 5,000 questions a day across
>    200 courses, routing to a human review queue. Cover the architecture (API, queue, workers, model,
>    database), local vs hosted model choice, latency and cost budgets, evaluation before each release,
>    privacy of student messages (student records laws such as FERPA, and what you may send to a vendor),
>    monitoring, and what happens when the model is down.

**You check:** read every answer. Rewrite at least one in your own words. Practice Q5 out loud with a timer
(5 minutes): system design rounds reward a clear structure (requirements → design → trade-offs → how you'd
measure it) more than any single detail. If an answer says something you can't explain, ask Claude about it until
you can.

**Write "How I used Claude Code" yourself** in `README.md`: what moving your teaching rules into user memory
changed, what `/memory` showed you, how typing `classify` by hand went, and which batch labels the model got wrong.

**Done when:**

```bash
python -m ruff check . && python -m ruff format --check . && python -m pytest
```

prints `All checks passed!`, `... already formatted` and `24 passed, 2 deselected`.

**Commit:** `Add README design notes and interview Q&A`

Then push and check CI:

```text
!git push
!gh run list --branch main --limit 1
```

Wait until the newest run shows `completed` and `success`. If it fails, open it with
`!gh run view <id> --log-failed`, then ask Claude to fix it.

---

## When you're done

Tell the roadmap chat **"done"**. It will review the repo, run the tests, and tick this row in the roadmap.

## Level up

**Put who you are in user memory, and what the repo needs in project memory.** Your teaching rules now follow you
into every project without copy-pasting, and each repo's `CLAUDE.md` stays short and true for anyone who clones
it. When Claude behaves oddly, run `/memory` first: it shows exactly which files shaped the session. Your user
memory isn't in any repo, so keep a copy in your `claude-project-kit` repo (for example `settings/CLAUDE.md`),
and a new laptop is one `cp` away from knowing how to teach you.

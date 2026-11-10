import argparse
import contextlib
import json
import os
from pathlib import Path
from typing import TextIO

from triage.classifier import TriageError, classify
from triage.evals import RowResult, fingerprint, format_report, load_golden, run_eval
from triage.llm import LLMClient, make_client
from triage.usage_log import UsageLog, summarize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="triage")
    parser.add_argument(
        "--provider",
        choices=["ollama", "fake"],
        default=os.environ.get("TRIAGE_PROVIDER") or "ollama",
    )
    parser.add_argument("--model", default=os.environ.get("TRIAGE_MODEL") or "qwen2.5:3b")
    parser.add_argument(
        "--ollama-url", default=os.environ.get("OLLAMA_URL") or "http://localhost:11434"
    )
    parser.add_argument("--log", type=Path, default=Path("logs/usage.jsonl"))

    subcommands = parser.add_subparsers(dest="command", required=True)
    classify_parser = subcommands.add_parser("classify")
    classify_parser.add_argument("question")
    batch_parser = subcommands.add_parser("batch")
    batch_parser.add_argument("file", type=Path)
    stats_parser = subcommands.add_parser("stats")
    price_help = "what-if price, USD per 1M input/output tokens"
    stats_parser.add_argument("--price-in", type=float, default=0.0, help=price_help)
    stats_parser.add_argument("--price-out", type=float, default=0.0, help=price_help)
    eval_parser = subcommands.add_parser("eval")
    eval_parser.add_argument("--golden", type=Path, default=Path("evals/golden.jsonl"))
    eval_parser.add_argument("--out", type=Path, default=Path("evals/results.json"))
    eval_parser.add_argument("--limit", type=int, default=None, help="only the first N examples")
    return parser


def _run_classify(
    question: str, client: LLMClient, log: UsageLog, stdout: TextIO, stderr: TextIO
) -> int:
    try:
        result = classify(question, client, log=log)
    except TriageError as err:
        print(f"error: {err}", file=stderr)
        return 1
    print(result.model_dump_json(indent=2), file=stdout)
    return 0


def _run_batch(path: Path, client: LLMClient, log: UsageLog, stdout: TextIO) -> int:
    exit_code = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        question = line.strip()
        if not question:
            continue
        try:
            result = classify(question, client, log=log)
        except TriageError as err:
            print(json.dumps({"question": question, "error": str(err)}), file=stdout)
            exit_code = 1
        else:
            print(json.dumps({"question": question, **result.model_dump()}), file=stdout)
    return exit_code


def _run_eval(
    args: argparse.Namespace, client: LLMClient, log: UsageLog, stdout: TextIO, stderr: TextIO
) -> int:
    try:
        examples = load_golden(args.golden)
        golden_fingerprint = fingerprint(args.golden)
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=stderr)
        return 1
    examples = examples[: args.limit]
    total = len(examples)

    def show_progress(index: int, _row: RowResult) -> None:
        print(f"{index}/{total}", end="\r", file=stderr, flush=True)

    report = run_eval(
        examples, client, fingerprint=golden_fingerprint, log=log, on_row=show_progress
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(format_report(report), file=stdout)
    print(f"saved {args.out}", file=stdout)
    return 0


def main(argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    log = UsageLog(args.log)
    if args.command == "stats":
        summary = summarize(log.read(), args.price_in, args.price_out)
        print(json.dumps(summary, indent=2), file=stdout)
        return 0

    client = make_client(args.provider, args.model, args.ollama_url)
    if args.command == "classify":
        return _run_classify(args.question, client, log, stdout, stderr)
    if args.command == "eval":
        return _run_eval(args, client, log, stdout, stderr)
    return _run_batch(args.file, client, log, stdout)

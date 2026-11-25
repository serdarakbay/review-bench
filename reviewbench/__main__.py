"""CLI entry point: python -m reviewbench <command>. Commands are added step by step."""

from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from reviewbench.config import ROOT, load_config

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """review-bench: measure how well LLMs review LLM-written code."""


@app.command("build-dataset")
def build_dataset(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing dataset file."),
    version: str = typer.Option("v1", help="v1: HumanEval (config 'dataset'); v2: subtle MBPP+ bugs ('dataset_v2')."),
) -> None:
    """Build a paired sample set: canonical solutions + one injected bug per task (output path from config)."""
    from reviewbench.dataset import build_samples, load_humaneval, load_mbppplus, write_jsonl

    if version not in ("v1", "v2"):
        console.print(f"[red]unknown version {version!r}[/] (v1 or v2)")
        raise typer.Exit(1)
    cfg = load_config()
    dcfg = cfg["dataset" if version == "v1" else "dataset_v2"]
    out = ROOT / dcfg["output"]
    if out.exists() and not force:
        console.print(f"[red]{out} already exists.[/] Use --force to overwrite.")
        raise typer.Exit(1)

    tasks = load_humaneval(cfg) if version == "v1" else load_mbppplus(dcfg["hf_name"], dcfg.get("exclude", []))
    samples = build_samples(
        tasks,
        n_tasks=dcfg["n_tasks"],
        seed=cfg["seed"],
        timeout_s=dcfg.get("test_timeout_s", cfg["sandbox"]["timeout_s"]),
        max_tries=dcfg["max_mutant_tries"],
        subtle=dcfg.get("subtle", False),
        on_task=lambda tid, op: console.print(f"  {tid:<10} -> {op or 'no usable mutant'}"),
    )
    write_jsonl(samples, out, force=force)

    counts = Counter(s["bug_type"] or "correct" for s in samples)
    table = Table(title=f"{out.relative_to(ROOT)}: {len(samples)} samples")
    table.add_column("bug_type")
    table.add_column("count", justify="right")
    for name, n in sorted(counts.items()):
        table.add_row(name, str(n))
    console.print(table)


@app.command("build-natural")
def build_natural(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing natural dataset file."),
    limit: int = typer.Option(0, help="Only the first N tasks (0 = all)."),
    source: str = typer.Option("humaneval", help="humaneval (config 'natural'), mbpp ('natural_mbpp') "
                                                  "or mbpp-gemini ('natural_mbpp_gemini': Gemini as writer)."),
) -> None:
    """A writer model solves tasks; failing solutions become natural-bug samples (output path from config)."""
    from reviewbench.dataset import load_humaneval, load_mbppplus, write_jsonl
    from reviewbench.dataset import with_tests_from
    from reviewbench.writer import ClaudeWriter, balance, build_natural_samples, build_writer, generate_solutions

    sections = {"humaneval": "natural", "mbpp": "natural_mbpp", "mbpp-gemini": "natural_mbpp_gemini"}
    if source not in sections:
        console.print(f"[red]unknown source {source!r}[/] ({', '.join(sections)})")
        raise typer.Exit(1)
    cfg = load_config()
    ncfg = cfg[sections[source]]
    out, raw_path = ROOT / ncfg["output"], ROOT / ncfg["raw"]
    if out.exists() and not force:
        console.print(f"[red]{out} already exists.[/] Use --force to overwrite.")
        raise typer.Exit(1)
    writer = build_writer(ncfg["writer"], raw_path)
    if isinstance(writer, ClaudeWriter) and not writer.exe:
        console.print("[red]claude CLI not found.[/]")
        raise typer.Exit(1)
    if hasattr(writer, "is_available") and not writer.is_available()[0]:
        console.print(f"[red]writer not available:[/] {writer.is_available()[1]}")
        raise typer.Exit(1)

    if source.startswith("mbpp"):
        tasks = load_mbppplus(ncfg["hf_name"], ncfg.get("exclude", []))
    else:
        tasks = load_humaneval(cfg)
    if limit:
        tasks = tasks[:limit]

    def show(row: dict) -> None:
        console.print(f"  {row['task_id']:<15} -> {row['error'] or 'ok'} ({row.get('latency_s')}s)")

    console.print(f"writer {writer.model}: {len(tasks)} tasks (cached ones are skipped)")
    cached = generate_solutions(tasks, writer, raw_path, on_done=show)

    # The writer always sees the original HumanEval prompt; only the tests may come from
    # a stricter suite (HumanEval+), which exposes bugs the original tests miss.
    test_tasks = tasks
    if ncfg.get("tests_hf_name"):
        test_tasks = with_tests_from(tasks, ncfg["tests_hf_name"], ncfg.get("exclude", []))
    timeout_s = ncfg.get("test_timeout_s", cfg["sandbox"]["timeout_s"])
    samples, stats = build_natural_samples(test_tasks, cached, timeout_s)
    if ncfg.get("balance"):
        samples = balance(samples, cfg["seed"])  # all bugs + as many correct samples, seeded
    write_jsonl(samples, out, force=force)
    tests = ncfg.get("tests_hf_name") or ncfg.get("hf_name") or cfg["dataset"]["hf_name"]
    console.print(f"{out.relative_to(ROOT)}: {len(samples)} samples | {stats} | tests: {tests}")


@app.command("run")
def run(
    reviewers: str = typer.Option("ollama", help="Comma-separated reviewer names."),
    prompts: str = typer.Option("", help="Comma-separated prompt keys (default: all in config.yaml)."),
    limit: int = typer.Option(0, help="Only the first N samples (0 = all)."),
    run_id: str = typer.Option("", help="Resume/extend this run id (default: new timestamped id)."),
    dataset: Path = typer.Option(None, help="Samples JSONL (default: dataset.output from config)."),
) -> None:
    """Run reviewers on the dataset; one JSON line per call in results/<run_id>/calls.jsonl."""
    from datetime import datetime

    from reviewbench.dataset import read_jsonl
    from reviewbench.reviewers import build_reviewer
    from reviewbench.reviewers.base import Prompt
    from reviewbench.runner import run_reviews

    cfg = load_config()
    samples = read_jsonl(dataset or ROOT / cfg["dataset"]["output"])
    if limit:
        samples = samples[:limit]
    prompt_keys = [p for p in prompts.split(",") if p] or cfg["prompts"]

    active = []
    for name in [r.strip() for r in reviewers.split(",") if r.strip()]:
        for key in prompt_keys:
            try:
                reviewer = build_reviewer(name, cfg, Prompt.load(key))
            except KeyError as e:
                console.print(f"[yellow]skip {name}:[/] {e}")
                break
            ok, reason = reviewer.is_available()
            if not ok:
                console.print(f"[yellow]skip {name}:[/] {reason}")
                break
            active.append(reviewer)
    if not active:
        console.print("[red]No reviewer available.[/]")
        raise typer.Exit(1)

    run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / "results" / run_id
    console.print(f"run {run_id}: {len(samples)} samples x {len(active)} reviewer/prompt pairs "
                  f"= up to {len(samples) * len(active)} calls (finished calls are skipped)")

    def show(r: dict) -> None:
        status = r["error"] or f"{r['verdict']} line={r['reported_line']}"
        truth = f"buggy@{r['bug_line']}" if r["is_buggy"] else "correct"
        console.print(f"  {r['reviewer']}/{r['prompt_name']} {r['sample_id']:<30} {truth:<10} -> {status} "
                      f"({r['latency_s']}s)")

    def quota(name: str, message: str) -> None:
        console.print(f"[red]{name}: quota exhausted, skipping its remaining calls "
                      f"(resume later with --run-id {run_id}).[/] {message}")

    written = run_reviews(samples, active, run_dir, on_call=show, on_quota=quota)
    console.print(f"{len(written)} calls written to {(run_dir / 'calls.jsonl').relative_to(ROOT)}")


def _fmt(rate) -> str:
    """'62.0% [52.1-71.0] (62/100)' for a Rate, '-' if empty."""
    if rate.value is None:
        return "-"
    lo, hi = rate.ci
    return f"{rate.value:.1%} [{lo:.0%}-{hi:.0%}] ({rate.k}/{rate.n})"


@app.command("report")
def report(
    run_dirs: list[Path] = typer.Argument(..., help="One or more results/<run_id> directories."),
    out: Path = typer.Option(None, help="Output dir for report.md + plots "
                                        "(default: the run dir, or results/report for several)."),
    adjudication: Path = typer.Option(None, help="JSON sample_id -> manual class; adds an adjudicated view."),
) -> None:
    """Metrics with Wilson 95% CI in the terminal; report.md, plots and McNemar comparisons on disk."""
    from reviewbench.report import load_calls, write_report
    from reviewbench.scoring import GROUP_KEYS, by_bug_type, group_by, summarize

    calls = load_calls(run_dirs)
    groups = group_by(calls, GROUP_KEYS)
    title = ", ".join(d.name for d in run_dirs)

    t = Table(title=f"{title}: {len(calls)} calls (rates with Wilson 95% CI)")
    for col in ("reviewer/model", "prompt", "catch rate", "localization", "false alarm", "precision", "F1",
                "parse fail", "errors", "latency", "cost"):
        t.add_column(col)
    for (reviewer, model, pname, pver), group in groups.items():
        s = summarize(group)
        t.add_row(f"{reviewer}/{model}", f"{pname}_{pver}", _fmt(s["catch_rate"]), _fmt(s["localization"]),
                  _fmt(s["false_alarm_rate"]), _fmt(s["precision"]),
                  "-" if s["f1"] is None else f"{s['f1']:.3f}", _fmt(s["parse_failure_rate"]),
                  str(s["n_errors"]), "-" if s["mean_latency_s"] is None else f"{s['mean_latency_s']:.1f}s",
                  f"${s['cost_usd']:.2f}")
    console.print(t)

    for (reviewer, model, pname, pver), group in groups.items():
        bt = Table(title=f"{reviewer}/{model} {pname}_{pver}: by bug type")
        for col in ("bug_type", "catch rate", "localization"):
            bt.add_column(col)
        for bug_type, m in by_bug_type(group).items():
            bt.add_row(bug_type, _fmt(m["catch_rate"]), _fmt(m["localization"]))
        console.print(bt)

    out_dir = out or (run_dirs[0] if len(run_dirs) == 1 else ROOT / "results" / "report")
    import json

    adj = json.loads(adjudication.read_text(encoding="utf-8")) if adjudication else None
    path = write_report(run_dirs, out_dir, adj)
    console.print(f"wrote {path} (+ rates.png, bug_types.png, cost_f1.png)")


@app.command("mutant-sheet")
def mutant_sheet(
    dataset: Path = typer.Option(None, help="Samples JSONL (default: dataset_v2.output)."),
    out: Path = typer.Option(None, help="Markdown output (default: docs/<dataset name>_sheet.md)."),
) -> None:
    """Manual-review sheet for MBPP+ mutants: task, diff, first failing MBPP+ input (expected vs got)."""
    import difflib
    from concurrent.futures import ThreadPoolExecutor

    from reviewbench.dataset import load_mbppplus, read_jsonl
    from reviewbench.sandbox import first_failure

    cfg = load_config()
    dcfg = cfg["dataset_v2"]
    dataset = dataset or ROOT / dcfg["output"]
    out = out or ROOT / "docs" / f"{dataset.stem}_sheet.md"
    samples = read_jsonl(dataset)
    correct = {s["task_id"]: s for s in samples if not s["is_buggy"]}
    buggy = [s for s in samples if s["is_buggy"]]
    tasks = {t.task_id: t for t in load_mbppplus(dcfg["hf_name"], dcfg.get("exclude", []))}

    def entry(s: dict) -> str:
        diff = difflib.unified_diff(correct[s["task_id"]]["code"].splitlines(), s["code"].splitlines(),
                                    "correct", "mutant", n=1, lineterm="")
        fail = first_failure(s["code"], tasks[s["task_id"]].test, dcfg["test_timeout_s"])
        task = s["task_prompt"].strip().strip('"').strip()
        return (f"### {s['sample_id']} (bug line {s['bug_line']})\n\n{task}\n\n"
                f"```diff\n" + "\n".join(list(diff)[2:]) + f"\n```\n\nFirst failing MBPP+ input:\n\n"
                f"```\n{fail}\n```\n\nclass: \n")

    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(entry, buggy))
    out.write_text(f"# Review sheet: {dataset.name} ({len(buggy)} mutants)\n\n" + "\n".join(entries),
                   encoding="utf-8")
    console.print(f"wrote {out}")


@app.command("review")
def review(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, help="Python file to review."),
    reviewer: str = typer.Option("", help="Reviewer name (default: best F1 in review.results)."),
    task: str = typer.Option("", help="What the code should do (default: reviewer infers it from the code)."),
    prompt: str = typer.Option("", help="Prompt key (default: review.prompt in config.yaml)."),
) -> None:
    """Review one file with one reviewer; the default reviewer is chosen from benchmark results."""
    from reviewbench.report import load_calls
    from reviewbench.review import NO_TASK, pick_reviewer, rank_reviewers
    from reviewbench.reviewers import build_reviewer
    from reviewbench.reviewers.base import PARSE_ERROR, Prompt

    cfg = load_config()
    rcfg = cfg["review"]
    p = Prompt.load(prompt or rcfg["prompt"])
    key = f"{p.name}_{p.version}"

    if reviewer:
        try:
            chosen = build_reviewer(reviewer, cfg, p)
        except KeyError as e:
            console.print(f"[red]{e.args[0]}[/]")
            raise typer.Exit(1)
        ok, why = chosen.is_available()
        if not ok:
            console.print(f"[red]{reviewer} is not available:[/] {why}")
            raise typer.Exit(1)
        reason = "chosen with --reviewer"
    else:
        built = {}
        for name in cfg["reviewers"]:
            try:
                r = build_reviewer(name, cfg, p)
            except KeyError:
                continue
            ok, why = r.is_available()
            if ok:
                built[name] = r
            else:
                console.print(f"[yellow]skip {name}:[/] {why}")
        dirs = [ROOT / d for d in rcfg["results"] if (ROOT / d / "calls.jsonl").exists()]
        models = {name: c["model"] for name, c in cfg["reviewers"].items()}
        ranking = rank_reviewers(load_calls(dirs), key, models)
        tol = rcfg.get("f1_tolerance", 0.0)
        picked = pick_reviewer(ranking, list(built), rcfg["fallback"], tol)
        rt = Table(title=f"benchmark ranking ({key}, {len(dirs)} runs; cost = API list-price equivalent)")
        for col in ("reviewer/model", "F1", "calls", "$/call", "available"):
            rt.add_column(col)
        for r in ranking:
            rt.add_row(f"{r['reviewer']}/{r['model']}", f"{r['f1']:.3f}", str(r["n"]),
                       f"{r['usd_per_call']:.4f}", "yes" if r["reviewer"] in built else "no")
        console.print(rt)
        if not picked:
            console.print("[red]No reviewer available.[/]")
            raise typer.Exit(1)
        chosen, reason = built[picked[0]], picked[1]

    console.print(f"reviewer {chosen.name}/{chosen.model}, prompt {key} ({reason})")
    code = file.read_text(encoding="utf-8")
    try:
        result = chosen.review(task or NO_TASK, code)
    except Exception as e:  # network, quota, CLI failure: report, do not crash with a traceback
        console.print(f"[red]review failed:[/] {type(e).__name__}: {e}")
        raise typer.Exit(1)

    if result.verdict == PARSE_ERROR:
        console.print("[red]PARSE_ERROR[/]: the reviewer did not answer in the expected JSON. Raw response:")
        console.print(result.raw_response, markup=False)
        raise typer.Exit(1)
    color = "red" if result.verdict == "BUG" else "green"
    console.print(f"[bold {color}]{result.verdict}[/]" + (f" at line {result.line}" if result.line else ""))
    lines = code.splitlines()
    if result.line and 1 <= result.line <= len(lines):
        console.print(f"  {result.line} | {lines[result.line - 1]}", markup=False, highlight=False)
    console.print(result.explanation, markup=False)
    cost = f", ${result.cost_usd:.4f}" if result.cost_usd else ""
    console.print(f"[dim]{result.latency_s:.1f}s{cost}[/]")


if __name__ == "__main__":
    app()

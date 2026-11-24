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
def build_dataset(force: bool = typer.Option(False, "--force", help="Overwrite an existing dataset file.")) -> None:
    """Build data/samples_v1.jsonl: HumanEval canonical solutions + one injected bug per task."""
    from reviewbench.dataset import build_samples, load_humaneval, write_jsonl

    cfg = load_config()
    out = ROOT / cfg["dataset"]["output"]
    if out.exists() and not force:
        console.print(f"[red]{out} already exists.[/] Use --force to overwrite.")
        raise typer.Exit(1)

    tasks = load_humaneval(cfg)
    samples = build_samples(
        tasks,
        n_tasks=cfg["dataset"]["n_tasks"],
        seed=cfg["seed"],
        timeout_s=cfg["sandbox"]["timeout_s"],
        max_tries=cfg["dataset"]["max_mutant_tries"],
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
    limit: int = typer.Option(0, help="Only the first N HumanEval tasks (0 = all 164)."),
) -> None:
    """Claude writes HumanEval solutions; failing ones become natural-bug samples (data/natural_v1.jsonl)."""
    from reviewbench.dataset import load_humaneval, write_jsonl
    from reviewbench.writer import ClaudeWriter, build_natural_samples, generate_solutions

    cfg = load_config()
    ncfg = cfg["natural"]
    out, raw_path = ROOT / ncfg["output"], ROOT / ncfg["raw"]
    if out.exists() and not force:
        console.print(f"[red]{out} already exists.[/] Use --force to overwrite.")
        raise typer.Exit(1)
    writer = ClaudeWriter(ncfg["writer"])
    if not writer.exe:
        console.print("[red]claude CLI not found.[/]")
        raise typer.Exit(1)

    tasks = load_humaneval(cfg)
    if limit:
        tasks = tasks[:limit]

    def show(row: dict) -> None:
        console.print(f"  {row['task_id']:<15} -> {row['error'] or 'ok'} ({row.get('latency_s')}s)")

    console.print(f"writer {writer.model}: {len(tasks)} tasks (cached ones are skipped)")
    cached = generate_solutions(tasks, writer, raw_path, on_done=show)
    samples, stats = build_natural_samples(tasks, cached, cfg["sandbox"]["timeout_s"])
    write_jsonl(samples, out, force=force)
    console.print(f"{out.relative_to(ROOT)}: {len(samples)} samples | {stats}")


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
    path = write_report(run_dirs, out_dir)
    console.print(f"wrote {path} (+ rates.png, bug_types.png, cost_f1.png)")


if __name__ == "__main__":
    app()

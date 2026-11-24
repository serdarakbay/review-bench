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

    written = run_reviews(samples, active, run_dir, on_call=show)
    console.print(f"{len(written)} calls written to {(run_dir / 'calls.jsonl').relative_to(ROOT)}")


if __name__ == "__main__":
    app()

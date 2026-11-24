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


if __name__ == "__main__":
    app()

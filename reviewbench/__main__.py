"""CLI entry point: python -m reviewbench <command>. Commands are added step by step."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """review-bench: measure how well LLMs review LLM-written code."""


if __name__ == "__main__":
    app()

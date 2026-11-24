"""Load HumanEval, verify canonical solutions, build the benchmark sample set."""

import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from reviewbench.config import load_config
from reviewbench.mutate import OPERATORS, Mutant, find_mutants
from reviewbench.sandbox import RunResult, run_tests

# Tie-break order when operator counts are equal: scarcest operator first
# (bool_op and remove_branch apply to the fewest HumanEval tasks).
OP_PRIORITY = ["bool_op", "remove_branch", "off_by_one", "arith_op", "comparison_flip", "wrong_return"]
assert sorted(OP_PRIORITY) == sorted(OPERATORS)


@dataclass
class Task:
    task_id: str
    prompt: str
    canonical_solution: str
    test: str
    entry_point: str

    @property
    def canonical_code(self) -> str:
        """Full function: HumanEval prompt (signature + docstring) + body."""
        return self.prompt + self.canonical_solution

    @property
    def prompt_lines(self) -> int:
        """Number of lines taken by the prompt; the solution body starts after them."""
        return self.prompt.count("\n")


def load_humaneval(cfg: dict | None = None) -> list[Task]:
    from datasets import load_dataset

    cfg = cfg or load_config()
    ds = load_dataset(cfg["dataset"]["hf_name"], split=cfg["dataset"]["split"])
    return [
        Task(
            task_id=row["task_id"],
            prompt=row["prompt"],
            canonical_solution=row["canonical_solution"],
            test=row["test"],
            entry_point=row["entry_point"],
        )
        for row in ds
    ]


def verify_canonical(tasks: list[Task], timeout_s: float, workers: int = 4) -> dict[str, RunResult]:
    """Run every canonical solution against its tests. Returns task_id -> result."""
    def check(t: Task) -> tuple[str, RunResult]:
        return t.task_id, run_tests(t.canonical_code, t.test, t.entry_point, timeout_s)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(check, tasks))


def _killing_mutant(task: Task, op: str, rng: random.Random, max_tries: int, timeout_s: float) -> Mutant | None:
    """A random mutant of the solution body that FAILS the tests (non-equivalent), or None."""
    mutants = find_mutants(task.canonical_code, op, min_line=task.prompt_lines)
    rng.shuffle(mutants)
    for m in mutants[:max_tries]:
        if not run_tests(m.code, task.test, task.entry_point, timeout_s).passed:
            return m
    return None


def _sample(task: Task, code: str, mutant: Mutant | None) -> dict:
    return {
        "sample_id": f"{task.task_id}#{mutant.operator if mutant else 'correct'}",
        "task_id": task.task_id,
        "task_prompt": task.prompt,
        "code": code,
        "is_buggy": mutant is not None,
        "bug_type": mutant.operator if mutant else None,
        "bug_line": mutant.bug_line if mutant else None,
        "mutation": mutant.description if mutant else None,
    }


def build_samples(tasks: list[Task], n_tasks: int, seed: int, timeout_s: float, max_tries: int = 5) -> list[dict]:
    """Paired design: each selected task gives one correct sample and one buggy sample.

    Tasks are taken in a seeded random order. For each task, the operator used
    least so far is tried first, so bug types end up roughly balanced.
    """
    rng = random.Random(seed)
    order = list(tasks)
    rng.shuffle(order)
    counts = {op: 0 for op in OP_PRIORITY}
    samples: list[dict] = []
    for task in order:
        if len(samples) == 2 * n_tasks:
            break
        if not run_tests(task.canonical_code, task.test, task.entry_point, timeout_s).passed:
            continue
        for op in sorted(OP_PRIORITY, key=lambda o: (counts[o], OP_PRIORITY.index(o))):
            mutant = _killing_mutant(task, op, rng, max_tries, timeout_s)
            if mutant:
                counts[op] += 1
                samples += [_sample(task, task.canonical_code, None), _sample(task, mutant.code, mutant)]
                break
    if len(samples) < 2 * n_tasks:
        raise ValueError(f"only {len(samples) // 2} usable tasks, wanted {n_tasks}")
    return samples


def write_jsonl(rows: list[dict], path: Path, force: bool = False) -> None:
    """Write rows as JSONL. Refuses to overwrite: datasets are never regenerated silently."""
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists (use --force to overwrite)")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


if __name__ == "__main__":
    cfg = load_config()
    tasks = load_humaneval(cfg)
    results = verify_canonical(tasks, cfg["sandbox"]["timeout_s"])
    failed = [tid for tid, r in results.items() if not r.passed]
    print(f"canonical solutions passing: {len(tasks) - len(failed)}/{len(tasks)}")
    for tid in failed:
        r = results[tid]
        print(f"  FAIL {tid} timed_out={r.timed_out} stderr={r.stderr[-300:]!r}")

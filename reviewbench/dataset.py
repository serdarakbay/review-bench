"""Load HumanEval, verify canonical solutions, build the benchmark sample set."""

import dataclasses
import json
import random
import re
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
    code_has_prompt: bool = True  # HumanEval: prompt is the code prefix; MBPP+: prompt is only the task text
    weak_test: str | None = None  # MBPP+: the original 3 MBPP asserts (much weaker than `test`)

    @property
    def canonical_code(self) -> str:
        """Full solution: HumanEval prompt (signature + docstring) + body, or the MBPP+ code alone."""
        return self.prompt + self.canonical_solution if self.code_has_prompt else self.canonical_solution

    @property
    def prompt_lines(self) -> int:
        """Number of prompt lines in canonical_code; the solution body starts after them."""
        return self.prompt.count("\n") if self.code_has_prompt else 0


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


def replace_tests(tasks: list[Task], rows: dict[str, dict], exclude: list[str]) -> list[Task]:
    """Same tasks (prompt unchanged) with tests and entry point taken from `rows`; drops `exclude` and unknown ids."""
    return [
        dataclasses.replace(t, test=rows[t.task_id]["test"], entry_point=rows[t.task_id]["entry_point"])
        for t in tasks
        if t.task_id in rows and t.task_id not in exclude
    ]


def with_tests_from(tasks: list[Task], hf_name: str, exclude: list[str]) -> list[Task]:
    """Swap in the tests of another HumanEval-format dataset (e.g. evalplus/humanevalplus)."""
    from datasets import load_dataset

    rows = {r["task_id"]: r for r in load_dataset(hf_name, split="test")}
    return replace_tests(tasks, rows, exclude)


def mbpp_prompt(text: str, first_test: str) -> str:
    """evalplus MBPP+ prompt: the task sentence and one example assert in a docstring.

    The assert fixes the function name and call signature, as in the official MBPP+ setup.
    """
    return f'"""\n{text}\n{first_test}\n"""\n'


def mbpp_entry_point(test: str) -> str:
    """Function name called by an MBPP+ test script (`assertion(name(*inp), exp, atol)`)."""
    names = set(re.findall(r"assertion\((\w+)\(\*inp\)", test))
    if len(names) != 1:
        raise ValueError(f"expected one entry point, found {sorted(names)}")
    return names.pop()


def load_mbppplus(hf_name: str, exclude: list[str]) -> list[Task]:
    """MBPP+ tasks as Task objects; task ids are 'Mbpp/<n>' as in evalplus."""
    from datasets import load_dataset

    tasks = []
    for r in load_dataset(hf_name, split="test"):
        task_id = f"Mbpp/{r['task_id']}"
        if task_id in exclude:
            continue
        imports = "\n".join(r["test_imports"])
        tasks.append(Task(
            task_id=task_id,
            prompt=mbpp_prompt(r["prompt"], r["test_list"][0]),
            canonical_solution=r["code"],
            test=(imports + "\n\n" if imports else "") + r["test"],
            entry_point=mbpp_entry_point(r["test"]),
            code_has_prompt=False,
            weak_test=(imports + "\n\n" if imports else "") + "\n".join(r["test_list"]) + "\n",
        ))
    return tasks


def verify_canonical(tasks: list[Task], timeout_s: float, workers: int = 4) -> dict[str, RunResult]:
    """Run every canonical solution against its tests. Returns task_id -> result."""
    def check(t: Task) -> tuple[str, RunResult]:
        return t.task_id, run_tests(t.canonical_code, t.test, t.entry_point, timeout_s)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(check, tasks))


def _killing_mutant(task: Task, op: str, rng: random.Random, max_tries: int, timeout_s: float,
                    subtle: bool = False) -> Mutant | None:
    """A random mutant of the solution body that FAILS the tests (non-equivalent), or None.

    subtle=True keeps only mutants that also PASS the task's weak tests: the bug shows only
    on inputs the original tests (and the example in the prompt) do not cover.
    """
    mutants = find_mutants(task.canonical_code, op, min_line=task.prompt_lines)
    rng.shuffle(mutants)
    for m in mutants[:max_tries]:
        # Weak tests first: they are fast and reject most mutants.
        if subtle and not run_tests(m.code, task.weak_test, task.entry_point, timeout_s).passed:
            continue
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


def build_samples(tasks: list[Task], n_tasks: int | None, seed: int, timeout_s: float,
                  max_tries: int | None = 5, subtle: bool = False, on_task=None) -> list[dict]:
    """Paired design: each selected task gives one correct sample and one buggy sample.

    Tasks are taken in a seeded random order. For each task, the operator used
    least so far is tried first, so bug types end up roughly balanced.
    subtle=True: buggy samples must pass the weak tests and fail the full tests.
    n_tasks=None takes every usable task; max_tries=None tries every mutant.
    on_task(task_id, operator or None) is called after each task, for progress output.
    """
    rng = random.Random(seed)
    order = list(tasks)
    rng.shuffle(order)
    counts = {op: 0 for op in OP_PRIORITY}
    samples: list[dict] = []
    for task in order:
        if n_tasks is not None and len(samples) == 2 * n_tasks:
            break
        if not run_tests(task.canonical_code, task.test, task.entry_point, timeout_s).passed:
            continue
        used = None
        for op in sorted(OP_PRIORITY, key=lambda o: (counts[o], OP_PRIORITY.index(o))):
            mutant = _killing_mutant(task, op, rng, max_tries, timeout_s, subtle)
            if mutant:
                counts[op] += 1
                samples += [_sample(task, task.canonical_code, None), _sample(task, mutant.code, mutant)]
                used = op
                break
        if on_task:
            on_task(task.task_id, used)
    if not samples or (n_tasks is not None and len(samples) < 2 * n_tasks):
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

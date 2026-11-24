"""Load HumanEval and verify canonical solutions."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from reviewbench.config import load_config
from reviewbench.sandbox import RunResult, run_tests


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


if __name__ == "__main__":
    cfg = load_config()
    tasks = load_humaneval(cfg)
    results = verify_canonical(tasks, cfg["sandbox"]["timeout_s"])
    failed = [tid for tid, r in results.items() if not r.passed]
    print(f"canonical solutions passing: {len(tasks) - len(failed)}/{len(tasks)}")
    for tid in failed:
        r = results[tid]
        print(f"  FAIL {tid} timed_out={r.timed_out} stderr={r.stderr[-300:]!r}")

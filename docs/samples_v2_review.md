# Manual review of the subtle mutants (samples_v2)

**Scope:** the 67 buggy samples in `data/samples_v2.jsonl`. Each is one AST mutation of an MBPP+ reference
solution that **passes the 3 original MBPP asserts** (one of which is shown to the reviewer as the example)
and **fails the MBPP+ tests**. 377 MBPP+ tasks were tried with every mutant of every operator; 67 gave
such a mutant. Each buggy sample is paired with the unmodified reference solution of the same task.

**Method:** `python -m reviewbench mutant-sheet` lists every mutant with its diff and the first MBPP+ input
where it fails (expected vs got, run in the sandbox): [samples_v2_sheet.md](samples_v2_sheet.md). I
classified each mutant by whether the task text (one sentence plus one example assert, all the reviewer
sees besides the code) makes the mutant's behaviour wrong. The classes are stored in
[samples_v2_adjudication.json](samples_v2_adjudication.json). This is a qualitative check, not used by
any metric; the dataset labels stay as the tests define them.

## Result

| class | meaning | count |
|---|---|---|
| visible_bug | the mutant breaks behaviour the task sentence or its example fixes, on an input the task admits | 60 |
| arguable | the task does not settle the failing case | 6 |
| out_of_spec | the mutant differs only on inputs outside what the task defines | 1 |

Most subtle mutants are real bugs a careful reader can find: the 3 weak asserts miss them, but the task
sentence does not. Typical cases: `x > 0` turned into `x >= 0` where the task says "positive",
`range(n - 1)` that skips the last element, a removed guard for negative numbers or an empty list.

## Non-visible cases

| sample | why |
|---|---|
| Mbpp/300#off_by_one | **out_of_spec.** The extra loop step multiplies by `(n + 1 - r) = 0`, so the result is unchanged for every normal `n`; it differs only when floats overflow (`n = 1000000`: reference `inf`, mutant `nan`). |
| Mbpp/137#remove_branch | **arguable.** The ratio of zeroes to non-zeroes for an all-zero array is undefined; the reference returns `inf`, the mutant raises `ZeroDivisionError`. |
| Mbpp/245#comparison_flip | **arguable.** Whether the decreasing part of a bitonic subsequence must be strictly decreasing is not stated; the failing input has a repeated value. |
| Mbpp/311#remove_branch | **arguable.** "Set the left most unset bit" is undefined for 0 and for all-ones numbers, which is what the removed guard handled. |
| Mbpp/607#remove_branch | **arguable.** The task does not say what to return when the pattern is not found; the reference returns `None`, the mutant crashes. |
| Mbpp/639#off_by_one | **arguable.** The task only says to remove names that start with a lowercase letter; the reference also requires the rest of the name to be lowercase. On the failing input the mutant is closer to the task sentence than the reference. |
| Mbpp/771#bool_op | **arguable.** The reference calls the empty expression unbalanced; the usual convention is that it is balanced. |

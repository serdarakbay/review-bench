# Manual review of the natural bugs (natural_plus_v1)

**Scope:** the 7 Claude Sonnet solutions (writer: `claude-sonnet-5-5`) that fail the HumanEval+
(`evalplus/humanevalplus`) tests and are therefore labelled `is_buggy` in `data/natural_plus_v1.jsonl`.

**Method:** for each task I ran Claude's solution and the HumanEval+ reference solution on the HumanEval+
inputs, in an isolated subprocess, and took the first input where they disagree. The observed outputs
below come from those runs. Whether Claude or the reference is right is my reading of the docstring: a
qualitative note, **not** used by any metric. The labels in the dataset stay as the tests define them.

## Result

| class | meaning | count |
|---|---|---|
| Claude bug | Claude's output contradicts the docstring | 2 |
| reference bug | Claude follows the docstring; the HumanEval+ reference does not | 3 |
| arguable | the docstring does not settle it | 2 |

Only 2 of the 7 "natural bugs" are clearly Claude's mistakes. Three are cases where the test oracle
itself is wrong (the same canonical defects found in [false_alarm_review.md](false_alarm_review.md)
reappear in HumanEval+). Natural-bug catch rates must be read with this in mind: a reviewer that says
`OK` on a "reference bug" sample is arguably right.

## Cases

| task | first differing input | Claude | reference | class |
|---|---|---|---|---|
| HumanEval/76 `is_simple_power` | `(0, 0)` | `False` | `True` | Claude bug: `0**1 == 0`, so 0 is a power of 0 |
| HumanEval/132 `is_nested` | `'[][][]'` | `True` | `False` | Claude bug: no bracket is nested (docstring: `'[][]'` → `False`) |
| HumanEval/91 `is_bored` | `'I'` | `1` | `0` | reference bug: the sentence "I" starts with the word "I" |
| HumanEval/99 `closest_integer` | `'-578000000007654321.12345'` | `-578000000007654321` | `-578000000007654272` | reference bug: the reference goes through `float` and loses precision |
| HumanEval/141 `file_name_check` | `'éxample.exe'` | `'No'` | `'Yes'` | reference bug: the name must start with a Latin letter; `é` is not one |
| HumanEval/116 `sort_array` | `[-2, -3, -4, -5, -6]` | `[-6, -5, -4, -3, -2]` | `[-4, -2, -6, -5, -3]` | arguable: Claude matches the docstring example; the docstring also says "non-negative" |
| HumanEval/151 `double_the_difference` | `[True, True, False, False, True, False, ...]` | `0` | `3` | arguable: "ignore numbers that are not integers" — is `True` an integer? (`bool` is an `int` in Python) |

## Reviewer verdicts

_Pending: filled in from run `natural-plus-v1` when it finishes._

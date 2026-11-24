# Manual review of Gemini's false alarms (samples_v1)

**Scope:** the 16 distinct "correct" samples (HumanEval canonical solutions) that `gemini-3.8-flash`
flagged as `BUG` in run `gemini-full-v1` (13 under `neutral_v1`, 13 under `adversarial_v1`, 10 shared).

**Method:** for each claim, I wrote a concrete input and ran the canonical solution on it in an isolated
subprocess, then compared the output with what the docstring asks for. The observed outputs below come
from those runs. The *classification* is my judgement: it is a qualitative note, it is **not** used by any
metric, and the reported false-alarm rates stay as measured.

## Classes

| class | meaning | count |
|---|---|---|
| real defect | wrong output for an input the docstring allows, shown by a counterexample | 7 |
| arguable | depends on how the docstring is read (input domain or behaviour not pinned down) | 6 |
| outside spec / non-functional | only in a case the docstring does not define, or a performance concern | 2 |
| reviewer wrong | the claim does not hold | 1 |

So 7 of Gemini's 16 false-alarm samples point at verified defects in the canonical solutions that the
HumanEval tests do not catch. "Correct" in this benchmark means "passes the HumanEval tests", which is
weaker than "matches the docstring"; the false-alarm rate is therefore an upper bound for every reviewer.

## Cases

| task | Gemini's claim | probe → observed output | class |
|---|---|---|---|
| HumanEval/91 `is_bored` | a sentence that is just "I" is not counted | `is_bored('I. I am here')` → `1` (two sentences start with the word "I") | real defect |
| HumanEval/95 `check_dict_case` | the loop `break`s after the second key, later keys are never checked | `{'a':1,'b':2,'C':3}` → `True` (mixed case, should be `False`) | real defect |
| HumanEval/123 `get_odd_collatz` | `n/2` is float division, loses precision for large `n` | `n = 2**60+1` → result differs from the exact integer sequence (4 vs 163 elements) | real defect |
| HumanEval/124 `valid_date` | `and`/`or` precedence rejects day 31 in every month | `'01-31-2000'` → `False` (January has 31 days) | real defect |
| HumanEval/140 `fix_spaces` | 2 trailing spaces become a single `_` | `'a  '` → `'a_'` (spaces become underscores: `'a__'`) | real defect |
| HumanEval/141 `file_name_check` | `isalpha()` accepts non-Latin letters | `'é.txt'` → `'Yes'` (must start with a Latin letter) | real defect |
| HumanEval/144 `simplify` | float division is wrong for large numbers | `simplify("100000000000000001/1", "1/10")` → `True` (not a whole number) | real defect |
| HumanEval/76 `is_simple_power` | `n <= 0` breaks the loop | `is_simple_power(2, 0)` → never returns (timeout) | arguable (domain of `n` unstated) |
| HumanEval/92 `any_int` | `bool` passes `isinstance(x, int)` | `any_int(True, False, 1)` → `True` | arguable (`bool` is an `int` in Python) |
| HumanEval/116 `sort_array` | disagrees with the docstring example for negatives | `[-2,-3,-4,-5,-6]` → `[-4,-2,-6,-5,-3]`; docstring example says `[-6,-5,-4,-3,-2]` | arguable (docstring says "non-negative" yet shows negatives; the tests expect the canonical output) |
| HumanEval/122 `add_elements` | negative two-digit numbers are excluded | `add_elements([-10, 5], 2)` → `5` | arguable (is `-10` "two digits"?) |
| HumanEval/150 `x_or_y` | `n <= 0` is treated as prime | `x_or_y(0,1,2)` → `1`, `x_or_y(-7,1,2)` → `1` | arguable (domain of `n` unstated) |
| HumanEval/162 `string_to_md5` | non-ASCII text crashes | `string_to_md5("café")` → `UnicodeEncodeError` | arguable (encoding unspecified) |
| HumanEval/63 `fibfib` | naive exponential recursion, docstring asks for "efficiently" | `fibfib(27)` takes 0.82 s, correct value | non-functional |
| HumanEval/94 `skjkasdkd` | `isPrime` returns `True` for 0 and 1 | `[1, 4, 6]` (no prime) → `1`; the docstring does not define the no-prime case | outside spec |
| HumanEval/75 `is_multiply_prime` | `is_prime(n < 2)` is wrong | never reached (loops start at 2); `8`, `30` → `True`, `1`, `2` → `False`; the explanation itself ends "Wait, is there any bug?" | reviewer wrong |

## Did the other reviewers flag the 7 real defects?

`B` = flagged BUG on that canonical sample (verdict only; the stated reason was not checked).

| task | claude neutral | claude adversarial | gemini neutral | gemini adversarial | qwen neutral | qwen adversarial |
|---|---|---|---|---|---|---|
| 91 | . | . | B | B | B | B |
| 95 | B | B | . | B | B | B |
| 123 | . | . | B | . | B | B |
| 124 | B | B | B | B | B | B |
| 140 | B | B | B | B | B | . |
| 141 | B | . | B | B | . | B |
| 144 | B | B | B | B | B | B |

## Side note: the only "natural bug"

Claude Sonnet (writer) passed 163 of 164 HumanEval tasks. The single failure is `HumanEval/116`, the
task whose docstring contradicts its own tests (row above): Claude's solution follows the docstring
example for negative numbers, and the tests expect the canonical behaviour instead.

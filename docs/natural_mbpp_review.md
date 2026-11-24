# Manual review of the natural bugs (natural_mbpp_v1)

**Scope:** the 46 Claude Sonnet solutions (writer: `claude-sonnet-5-5`, prompt `writer_mbpp_v1`) that fail
the MBPP+ (`evalplus/mbppplus`) tests and are therefore labelled `is_buggy` in `data/natural_mbpp_v1.jsonl`.
Claude solved 377 MBPP+ tasks; 331 passed, 46 failed. The dataset holds the 46 failures plus 46 passing
solutions drawn with seed 42.

**Method:** for each task I ran Claude's solution on the MBPP+ inputs in an isolated subprocess and took
the first input where the test's own `assertion()` fails. The observed outputs below come from those runs
(Mbpp/300 timed out; for Mbpp/630 the failure is read from the reference code and the first 3-D input). Whether Claude or the
test oracle is right is my reading of the task sentence **and** its example assert, which the writer and
the reviewers both see. It is a qualitative note, **not** used by any metric; the dataset labels stay as
the tests define them. The classes are stored in [natural_mbpp_v1_adjudication.json](natural_mbpp_v1_adjudication.json).

## Result

| class | meaning | count |
|---|---|---|
| Claude bug | Claude's output contradicts the task sentence or its example, on an input the task admits | 10 |
| reference bug | Claude follows the task; the MBPP+ reference (test oracle) does not | 15 |
| arguable | the task does not settle it (unstated edge case, input outside the stated precondition, or the sentence and example disagree) | 21 |

Only 10 of the 46 "natural bugs" are clearly Claude's mistakes. MBPP task sentences are one line long, so
most failures come from behaviour the tests expect but the task never states, or from oracle defects.
Natural-bug catch rates on this set must be read with this in mind: a reviewer that says `OK` on a
"reference bug" sample is arguably right.

## Cases

`got` = Claude's output, `exp` = what the test expects (the reference's output).

### Claude bugs (10)

| task | first failing input | got | exp | why |
|---|---|---|---|---|
| Mbpp/16 `text_lowercase_underscore` | `'a_b_c_…_z'` | `False` | `True` | regex allows exactly two lowercase runs; the task says "sequences … joined with an underscore" |
| Mbpp/109 `odd_Equivalent` | `('10000100110011', 3)` | `0` | `1` | off by one: after k left rotations the last bit is `s[k-1]`, the code reads `s[k]` |
| Mbpp/138 `is_Sum_Of_Powers_Of_Two` | `-14` | `True` | `False` | a negative number is not a sum of positive powers of 2 |
| Mbpp/244 `next_Perfect_Square` | `3.14` | `TypeError` | `4` | crashes on any float ("a given number"); all 80 failures are floats |
| Mbpp/261 `division_elements` | `(5,2,3,3), (5,2,3,4)` | `(1,1,1,0)` | `(1.0,1.0,1.0,0.75)` | floor division instead of "mathematical division" |
| Mbpp/409 `min_product_tuple` | `[(7,2),(12,9),(-5,6),(8,-3),(0,0)]` | `0` | `-30` | takes `abs()` of each product; the minimum product is -30 |
| Mbpp/589 `perfect_squares` | `(-10, -1)` | `ValueError` | `[]` | `math.isqrt` crashes whenever a bound is negative |
| Mbpp/757 `count_reverse_pairs` | list with `'defed'` twice | `0` | `1` | skips palindromes, so two equal palindromes are never counted as a pair |
| Mbpp/780 `find_combinations` | `[(1,2,3),(3,4,5)]` | `[(4,6)]` | `[(4,6,8)]` | assumes 2-tuples; the task says "tuples" |
| Mbpp/792 `count_list` | `[2, 3, [4, [5, …]]]` | `3` | `1` | returns `len()`, counting non-list elements as lists |

### Reference bugs (15)

| task | first failing input | got | exp | why the oracle is wrong |
|---|---|---|---|---|
| Mbpp/74 `is_samepatterns` | `['red']*6, ['a','b','c','a','b','c']` | `False` | `True` | one colour cannot follow three different pattern letters |
| Mbpp/113 `check_integer` | `''` | `False` | `None` | the oracle returns `None`, not a boolean |
| Mbpp/160 `find_solution` | `(25, 123, 7)` | `(79, -16)` | `None` | 25·79 + 123·(−16) = 7 is a valid integer solution |
| Mbpp/294 `max_val` | `['3.14', False, 7.5]` | `7.5` | `False` | the oracle ignores floats and counts `False` as a number |
| Mbpp/410 `min_val` | `['Python', 10, 5, 2.5, 2.5, 'version']` | `2.5` | `5` | the oracle ignores floats |
| Mbpp/451 `remove_whitespaces` | `'\n\t'` | `''` | `'\n\t'` | the oracle removes only spaces, not "all whitespaces" |
| Mbpp/459 `remove_uppercase` | `'ThiS%^%!s&a(mY)TesTStR%i*ng'` | `'hi%^%!s&a(m)est%i*ng'` | `'hisamesting'` | the oracle also removes punctuation |
| Mbpp/593 `removezero_ip` | `'0.0.0.0'` | `'0.0.0.0'` | `'0...'` | the oracle deletes zero octets entirely |
| Mbpp/620 `largest_subset` | `[9,3,12,7,16,3,11,8,4,13,13]` | `3` | `4` | brute force gives 3; the oracle does not check all pairs |
| Mbpp/639 `sample_nam` | `['AbCdE','fGH','IJKLMnOp','qrs','TUVW','xyz']` | `17` | `0` | the oracle also drops names that are not lowercase after the first letter |
| Mbpp/739 `find_Index` | `100` | exact integer | float-rounded integer | the oracle uses float `sqrt` and loses precision for large n |
| Mbpp/771 `check_expression` | `''` | `True` | `False` | the empty expression is balanced |
| Mbpp/790 `even_position` | `[2,1,4,2,6,1,8,2,10,1,12]` | `True` | `False` | every even index holds an even number; the oracle also checks odd indices |
| Mbpp/800 `remove_all_spaces` | `'python\nprogram'` | `'pythonprogram'` | `'python\nprogram'` | the oracle removes only spaces, not "all whitespaces" |
| Mbpp/806 `max_run_uppercase` | `'Aaa'` | `1` | `0` | the oracle misses a run at the start of the string |

### Arguable (21)

| task | first failing input | got | exp | why it is unsettled |
|---|---|---|---|---|
| Mbpp/92 `is_undulating` | `82` | `False` | `True` | is a 2-digit number undulating? definitions differ |
| Mbpp/102 `snake_to_camel` | `'___python_program'` | `'PythonProgram'` | `'___PythonProgram'` | leading underscores are not specified |
| Mbpp/119 `search` | `[]` | `IndexError` | `0` | inputs break the precondition (sorted, exactly one single element) |
| Mbpp/223 `is_majority` | `([], 1, 0)` | `IndexError` | `False` | `n` does not match the array length |
| Mbpp/278 `count_first_elements` | `(1, 2, 3, 4, 5, 6)` | `6` | `5` | no tuple element at all: the answer is undefined |
| Mbpp/300 `count_binary_seq` | `1000000` (timed out) | slow exact `comb` | float sum (`inf`) | the formula is right; the test wants the oracle's float overflow and speed |
| Mbpp/305 `start_withp` | `['python Programming', …, 'PHP Programming']` | `('python','Programming')` | `('PHP','Programming')` | the task says letter `'p'`, the example and oracle use uppercase `P` |
| Mbpp/398 `sum_of_digits` | `[10, -5, 'abc', 0, 3.14]` | `6` | `14` | are the digits of `3.14` counted? |
| Mbpp/406 `find_Parity` | `2` | `True` | `False` | "parity" as bit parity (Claude) or odd/even (oracle) |
| Mbpp/415 `max_Product` | `[0,-1,-2,-4,5,0,-6]` | `(-6,-4)` | `(-4,-6)` | order of the returned pair is not specified |
| Mbpp/427 `change_date_format` | `'2021-1-026'` | `'026-1-2021'` | `'02-1-20216'` | input is not a valid yyyy-mm-dd date |
| Mbpp/446 `count_Occurrence` | `(1,1,1,2,2,2,3,3,3), [1,1,2,2,3,3]` | `9` | `18` | duplicates in the list: count once or twice? |
| Mbpp/468 `max_product` | `[3, 100, 4, 5, 150, 6]` | `45000` | `3000` | the example contradicts the sentence: 3·100·150 is an increasing subsequence |
| Mbpp/556 `find_Odd_Pair` | `([5,2,6,8], -3)` | `-4` | `0` | negative length argument |
| Mbpp/558 `digit_distance_nums` | `(12345, 9)` | `14` | `8` | numbers of different length: align by place value (Claude) or from the left (oracle) |
| Mbpp/559 `max_sub_array_sum` | `([], 0)` | `IndexError` | `0` | is the empty sublist allowed (all-negative lists too)? |
| Mbpp/576 `is_Sub_Array` | `[1,2,3,4,5], [1,3,5]` | `False` | `True` | "sublist": contiguous (Claude) or subsequence (oracle) |
| Mbpp/577 `last_Digit_Factorial` | `2.5` | `TypeError` | `0` | factorial of a non-integer or negative number |
| Mbpp/597 `find_kth` | `([1,2,3,1], [], 3)` | `3` | `2` | input array is not sorted |
| Mbpp/630 `get_coordinates` | `(1, 1, 1)` | `ValueError` | 27 neighbours | the example is 2-D; the oracle generalises to n-D |
| Mbpp/735 `toggle_middle_bits` | `True` | `True` | `3` | `bool` input; toggling the middle bits of 1 is undefined |

## Reviewer verdicts (run `natural-mbpp-v1`)

Per-sample verdicts are in the "Adjudicated view" of `results/natural-mbpp-v1/report.md`
(`python -m reviewbench report results/natural-mbpp-v1 --adjudication docs/natural_mbpp_v1_adjudication.json`).
Counts of `BUG` verdicts per class (counted from `results/natural-mbpp-v1/calls.jsonl`):

| reviewer / prompt | Claude bug (10) | reference bug (15) | arguable (21) | correct (46) |
|---|---|---|---|---|
| claude-sonnet-5-5 / adversarial_v1 | 5 | 0 | 3 | 0 |
| claude-sonnet-5-5 / neutral_v1 | 4 | 0 | 2 | 0 |
| gemini-3.8-flash / adversarial_v1 | 4 | 0 | 0 | 1 |
| gemini-3.8-flash / neutral_v1 | 4 | 0 | 1 | 2 |
| qwen3.5:9b / adversarial_v1 | 5 | 5 | 6 | 7 |
| qwen3.5:9b / neutral_v1 | 6 | 2 | 8 | 13 |

What this shows, qualitatively (10 real bugs are still too few for firm conclusions):

- **Claude, reviewing code Claude wrote, caught about half of its own real bugs** (4–5 of 10), as many
  as Gemini (4 of 10). The HumanEval+ result ("Claude flagged neither of its own two bugs, Gemini caught
  them") rested on n=2 and does not repeat here.
- **Claude and Gemini never flagged a reference-bug sample** (0 of 15): where the test oracle is wrong,
  they agree with the task instead of the tests. This is why their raw catch rates look low.
- **Qwen flags the most real bugs (5–6 of 10) but also 2–5 reference-bug samples and 7–13 of 46 correct
  samples.** Its BUG verdicts separate buggy from correct code much less than Claude's or Gemini's.
- Three Claude bugs (Mbpp/780, Mbpp/792 and, for most reviewers, Mbpp/589) were missed by almost everyone:
  they only show on inputs the example does not hint at (3-tuples, mixed lists, negative bounds).

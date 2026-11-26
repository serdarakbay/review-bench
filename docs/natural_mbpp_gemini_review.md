# Manual review of the natural bugs written by Gemini (natural_mbpp_gemini_v1)

**Scope:** the 60 Gemini 3.8 Flash solutions (writer prompt `writer_mbpp_v1`, the same prompt Claude got)
that fail the MBPP+ (`evalplus/mbppplus`) tests and are therefore labelled `is_buggy` in
`data/natural_mbpp_gemini_v1.jsonl`. Gemini solved 377 MBPP+ tasks; 317 passed, 60 failed. The dataset
holds the 60 failures plus 60 passing solutions drawn with seed 42.

**Method:** the same as for Claude's solutions ([natural_mbpp_review.md](natural_mbpp_review.md)): each
solution was run on the MBPP+ inputs in the sandbox, the first failing input was compared with the task
sentence and its example assert (all the writer and the reviewers see), and the failure was classed.
Failures that match a case already classed for Claude got the same class. Classes are stored in
[natural_mbpp_gemini_v1_adjudication.json](natural_mbpp_gemini_v1_adjudication.json). This is one
person's reading, not used by any metric.

## Result

| class | meaning | count |
|---|---|---|
| Gemini bug | Gemini's output contradicts the task sentence or its example, on an input the task admits | 10 |
| reference bug | Gemini follows the task; the MBPP+ reference (test oracle) does not | 16 |
| arguable | the task does not settle it (unstated edge case, input outside the stated precondition, or the sentence and example disagree) | 34 |

As with Claude (10 of 46), only 10 of the 60 test failures are clearly the writer's mistakes. Gemini fails
more MBPP+ tests than Claude (60 against 46), but has the same number of real bugs.

## Gemini bugs (10)

| task | first failing input | got | expected | why |
|---|---|---|---|---|
| Mbpp/99 `decimal_to_binary` | `-5` | `'b101'` | `'-101'` | `bin(n)[2:]` cuts the minus sign into a broken string |
| Mbpp/124 `angle_complex` | `(0, 1j)` (the example) | `π` | `π/2` | `complex(a, b)` with `b = 1j` gives `-1`; fails the task's own example |
| Mbpp/138 `is_Sum_Of_Powers_Of_Two` | `-14` | `True` | `False` | same bug as Claude: no `n > 0` check |
| Mbpp/239 `get_total_number_of_sequences` | `(10, 4)` (the example) | `ValueError` | `4` | the recursion reaches `n = 0` and shifts by `-1` |
| Mbpp/244 `next_Perfect_Square` | `3.14` | `TypeError` | `4` | same bug as Claude: `math.isqrt` on a float |
| Mbpp/260 `newman_prime` | `3` (the example) | `17` | `7` | counts primes in the sequence instead of following the example's indexing |
| Mbpp/261 `division_elements` | `(5,2,3,3), (5,2,3,4)` | `(1,1,1,0)` | `(1.0,1.0,1.0,0.75)` | same bug as Claude: floor division |
| Mbpp/765 `is_polite` | `1` | `2` | `3` | 2 is not a polite number (powers of 2 are not) |
| Mbpp/769 `Diff` | the example | `None` | `[10, 20, 30, 15]` | the body is a long comment trying to reproduce set order; it never returns |
| Mbpp/780 `find_combinations` | `[(1,2,3),(3,4,5)]` | `[(4,6)]` | `[(4,6,8)]` | same bug as Claude: assumes 2-tuples |

Four of Gemini's bugs (124, 239, 260, 769) fail the example assert in the task itself, which the writer
could see (checked by running each solution on that assert); all 10 of Claude's real bugs pass it. Four bugs (138, 244, 261, 780) are the same mistakes Claude made.

## Reference bugs (16)

Mbpp/74, 113, 160, 294, 410, 451, 459, 593, 620, 639, 739, 759, 771, 790, 800, 806. Most are the same
oracle defects found with Claude's solutions (e.g. `remove all whitespaces` that only removes spaces,
`max`/`min` of a heterogeneous list that ignores floats or counts `False`). New ones: Mbpp/759 (the
oracle rejects `-123.11` as a decimal number) and Mbpp/739 (the oracle rounds a float square root, so it
is wrong for large `n`; Gemini's exact integer answer is right).

## Arguable (34)

Empty inputs (Mbpp/119, 125, 559, 604), inputs outside the stated precondition (a length
argument that does not match the list, unsorted input to a "sorted array" task, floats or booleans
where the task implies integers), and unstated conventions (Mbpp/92 two-digit undulating numbers, Mbpp/311
all-ones numbers, Mbpp/406 "parity" read as the bit-count parity, Mbpp/602 returning the string `"None"`
when no character repeats).

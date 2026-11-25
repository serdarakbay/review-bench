# Right verdict, right reason? (manual review of the 12 real Claude bugs)

**Scope:** the 12 natural bugs that manual review confirmed as Claude's mistakes: 2 in `natural_plus_v1`
(HumanEval+) and 10 in `natural_mbpp_v1` (MBPP+); see [natural_bugs_review.md](natural_bugs_review.md) and
[natural_mbpp_review.md](natural_mbpp_review.md). Natural bugs have no known bug line, so localization
cannot tell a real catch from a lucky `BUG`. Here every `BUG` verdict on these 12 samples is read by hand.

**Method:** for each `BUG`, I compared the reviewer's explanation with the defect found by running the code
on the failing MBPP+/HumanEval+ input. Classes:

- **right**: names the actual defect (the mechanism or a failing input that shows it).
- **partial**: points at the right spot but misdescribes the defect or the fix.
- **wrong**: describes a problem that is not there or not the failing behaviour, or the explanation itself
  concludes the code is correct.

This is one person's reading, not a metric; no number in the main tables depends on it.

## Result

| reviewer | prompt | BUG on the 12 real bugs | right | partial | wrong |
|---|---|---|---|---|---|
| Claude Sonnet 5.5 | neutral | 4 | 4 | 0 | 0 |
| Claude Sonnet 5.5 | adversarial | 5 | 4 | 0 | 1 |
| Gemini 3.8 Flash | neutral | 5 | 4 | 1 | 0 |
| Gemini 3.8 Flash | adversarial | 5 | 4 | 0 | 1 |
| Gemini 4 Argon | neutral | 4 | 4 | 0 | 0 |
| Gemini 3.5 Flash-Lite | neutral | 5 | 2 | 1 | 2 |
| Gemini 3.5 Flash-Lite | adversarial | 6 | 2 | 2 | 2 |
| Qwen 3.5 9B | neutral | 8 | 2 | 0 | 6 |
| Qwen 3.5 9B | adversarial | 6 | 1 | 0 | 5 |

- **The strong reviewers flag less, but when they flag they are almost always right.** Claude, Gemini
  Flash and Argon give the actual defect in 20 of their 23 `BUG`s on these samples (1 partial, 2 wrong).
- **Qwen's higher catch count on real bugs is mostly luck.** It flags 8 (neutral) and 6 (adversarial)
  of the 12, the most of any reviewer, but names the actual defect only 2 and 1 times. Its "extra" catches
  come from wrong reasons (empty strings, `ZeroDivisionError`, an imagined infinite loop).
- **Flash-Lite sits in between**: about half of its `BUG`s on real bugs give the right reason.
- Counting only **right** reasons, the ranking on real bugs flips compared with raw flags: Claude, Gemini
  Flash and Argon (4 each) are ahead of Flash-Lite (2) and Qwen (1–2).

## Cases

`R` = right, `P` = partial, `W` = wrong, `.` = said OK or parse error (no reason to grade). `n` = neutral, `a` = adversarial prompt.

| sample | defect | Claude n | Claude a | Flash n | Flash a | Argon n | Lite n | Lite a | Qwen n | Qwen a |
|---|---|---|---|---|---|---|---|---|---|---|
| HumanEval/76 | `(0, 0)` returns False; 0 is a power of 0 | . | . | . | W | . | W | W | W | W |
| HumanEval/132 | `'[][][]'` returns True: opens are zipped with reversed closes | . | . | R | . | . | R | P | W | . |
| Mbpp/16 | regex accepts exactly two lowercase runs | . | . | P | . | . | P | P | W | W |
| Mbpp/109 | reads `s[(i+1) % len]` instead of `s[i % len]` | R | R | R | R | R | W | W | W | W |
| Mbpp/138 | returns True for 0 and negative even numbers | . | . | . | . | . | . | R | R | R |
| Mbpp/244 | `math.isqrt` raises `TypeError` on floats | R | W | . | . | R | . | . | W | . |
| Mbpp/261 | floor division `//` instead of `/` | . | R | . | . | . | . | . | R | W |
| Mbpp/409 | `abs()` hides negative products | R | R | R | R | . | R | R | . | . |
| Mbpp/589 | `math.isqrt` raises `ValueError` on negative bounds | . | . | . | R | R | . | . | . | . |
| Mbpp/757 | duplicate palindromes are never counted | R | R | R | R | R | . | . | W | W |
| Mbpp/780 | assumes 2-tuples | . | . | . | . | . | . | . | . | . |
| Mbpp/792 | returns `len()` instead of counting sub-lists | . | . | . | . | . | . | . | . | . |

Notes on the non-obvious grades:

- **Mbpp/16, Gemini Flash and Flash-Lite (P):** they see that the pattern allows only one underscore-joined
  pair, but blame the `^…$` anchors and want a "contains" match; the defect is the missing repetition
  `(_[a-z]+)*`.
- **HumanEval/132, Flash-Lite adversarial (P):** right mechanism, but its example `'[[]][['` is handled
  correctly by the code.
- **Mbpp/138, Flash-Lite and Qwen (R):** they name `n = 0`; the reference is `n > 0 and n % 2 == 0`, so 0
  fails for the same missing `n > 0` check as the negative inputs.
- **Mbpp/244, Claude adversarial (W):** the explanation concludes "the real issue is none"; only the verdict
  says `BUG`.
- **HumanEval/76, Flash-Lite adversarial (W):** a long trace that ends with "the verdict is OK".

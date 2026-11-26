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

## Personas (Week 5, Claude Sonnet 5.5)

Same grading for Claude with the three persona system prompts selected in stage 1 (runs `personas-v2-mbpp`
and `personas-v2-plus`; user prompt `neutral_v1`). `ag` = agency-code-reviewer, `ws` =
wshobson-security-auditor, `vq` = voltagent-qa-expert; Claude neutral repeated from the table above.

| sample | Claude n | ag | ws | vq |
|---|---|---|---|---|
| Mbpp/16 | . | . | W | . |
| Mbpp/109 | R | R | R | R |
| Mbpp/138 | . | R | . | R |
| Mbpp/244 | R | W | R | . |
| Mbpp/261 | . | R | . | R |
| Mbpp/409 | R | R | R | R |
| Mbpp/589 | . | . | . | . |
| Mbpp/757 | R | R | R | R |
| Mbpp/780 | . | . | . | . |
| Mbpp/792 | . | . | . | . |
| HumanEval/76 | . | W | . | . |
| HumanEval/132 | . | . | . | . |

| Claude Sonnet 5.5 | BUG on the 12 real bugs | right | partial | wrong |
|---|---|---|---|---|
| neutral | 4 | 4 | 0 | 0 |
| agency-code-reviewer | 7 | 5 | 0 | 2 |
| wshobson-security-auditor | 5 | 4 | 0 | 1 |
| voltagent-qa-expert | 5 | 5 | 0 | 0 |

- **A persona adds at most one right reason.** agency-code-reviewer and voltagent-qa-expert each find one
  real bug more than neutral for the right reason (Mbpp/138 or Mbpp/261 instead of Mbpp/244);
  wshobson-security-auditor finds the same 4. The extra raw flags of agency-code-reviewer are partly
  wrong reasons.

- **Mbpp/16, ws (W):** blames `$` matching before a trailing newline; the actual defect, the missing
  repetition of `_[a-z]+`, is not mentioned.
- **HumanEval/76, ag (W):** blames an iteration cap of 200 for huge powers; the failing case is
  `(0, 0)`.
- **Mbpp/244, ag (W):** the explanation concludes "there is no real bug"; only the verdict says `BUG`.
- **Mbpp/138 and Mbpp/261, ag and vq (R):** the two real bugs that Claude neutral misses: the missing
  `n > 0` check and floor division `//` where the task asks for division.

## Gemini as writer (writer × reviewer matrix)

The same grading on the 10 real bugs in Gemini 3.8 Flash's MBPP+ solutions
([natural_mbpp_gemini_review.md](natural_mbpp_gemini_review.md)), run `natural-mbpp-gemini-v1`.

| sample | defect | Claude n | Claude a | Flash n | Argon n | Lite n | Qwen n |
|---|---|---|---|---|---|---|---|
| Mbpp/99 | `bin(n)[2:]` breaks negative numbers | . | . | . | . | P | . |
| Mbpp/124 | `complex(0, 1j)` is `-1`; fails the example | R | R | . | . | W | W |
| Mbpp/138 | no `n > 0` check | . | . | . | . | W | W |
| Mbpp/239 | negative shift before the base case; fails the example | R | R | W | R | . | W |
| Mbpp/244 | `math.isqrt` on a float | W | . | . | . | . | . |
| Mbpp/260 | counts primes instead of terms; fails the example | R | R | R | P | W | P |
| Mbpp/261 | floor division | . | . | . | . | . | R |
| Mbpp/765 | formula without the `n + 1` shift | R | R | R | R | W | P |
| Mbpp/769 | no `return`; fails the example | R | R | R | R | R | R |
| Mbpp/780 | assumes 2-tuples | . | . | . | . | W | . |

| reviewer | prompt | BUG on the 10 real Gemini bugs | right | partial | wrong |
|---|---|---|---|---|---|
| Claude Sonnet 5.5 | neutral | 6 | 5 | 0 | 1 |
| Claude Sonnet 5.5 | adversarial | 5 | 5 | 0 | 0 |
| Gemini 3.8 Flash (same model as the writer) | neutral | 4 | 3 | 0 | 1 |
| Gemini 4 Argon | neutral | 4 | 3 | 1 | 0 |
| Gemini 3.5 Flash-Lite | neutral | 7 | 1 | 1 | 5 |
| Qwen 3.5 9B (local) | neutral | 7 | 2 | 2 | 3 |

- **Mbpp/239, Flash (W):** blames recursion depth for large `m`; the crash is the negative shift, on the
  example itself.
- **Mbpp/260, Argon (P):** right mechanism (the primality filter), wrong output (says 239, the code
  returns 17).
- **Mbpp/244, Claude neutral (W):** the explanation concludes "the code is correct".
- **Qwen (neutral):** right on 261 (floor division) and 769 (no `return`). Partial on 260 (traces the
  output 17 against the expected 7 correctly, but blames the initial values instead of counting primes)
  and 765 (says the formula is wrong, with a wrong example value). Wrong on 124 (claims `complex(1, 2)`
  adds the numbers), 138 (claims 3 is a sum of non-zero powers of 2) and 239 (blames the recurrence; the
  crash is the negative shift).
- **Flash-Lite** flags the most but gives the right reason once: e.g. Mbpp/124 "the test passes a single
  complex number" (it passes two arguments), Mbpp/138 "any integer greater than 1 is a sum of powers of 2".

Claude with the three personas on the same 10 Gemini bugs (same run): every `BUG` gives the right reason
except Mbpp/244, which all three flag with an explanation that concludes the code is correct (W).
agency-code-reviewer 8 flags (7 right: 99, 124, 239, 260, 261, 765, 769), wshobson-security-auditor 8 (7
right, the same set), voltagent-qa-expert 7 (6 right: without 261).

## Personas, Qwen 3.5 9B

Same grading for Qwen with the three personas, on Claude's 12 real bugs (runs `personas-v2-mbpp` and
`personas-v2-plus`, neutral re-run in the same batch) and on Gemini's 10 real bugs (run
`natural-mbpp-gemini-v1`; neutral graded above). `ag` = agency-code-reviewer, `ws` =
wshobson-security-auditor, `vq` = voltagent-qa-expert.

| sample (writer) | Qwen n (same batch) | ag | ws | vq |
|---|---|---|---|---|
| Mbpp/16 (Claude) | P | W | W | W |
| Mbpp/109 (Claude) | P | P | W | P |
| Mbpp/138 (Claude) | R | R | R | W |
| Mbpp/244 (Claude) | W | W | W | W |
| Mbpp/261 (Claude) | W | R | R | W |
| Mbpp/409 (Claude) | . | R | . | R |
| Mbpp/589 (Claude) | . | . | . | . |
| Mbpp/757 (Claude) | W | . | P | P |
| Mbpp/780 (Claude) | W | W | . | . |
| Mbpp/792 (Claude) | . | . | . | . |
| HumanEval/76 (Claude) | W | W | W | W |
| HumanEval/132 (Claude) | W | W | W | . |
| Mbpp/99 (Gemini) | . | . | . | . |
| Mbpp/124 (Gemini) | W | W | W | P |
| Mbpp/138 (Gemini) | W | P | W | W |
| Mbpp/239 (Gemini) | W | W | W | W |
| Mbpp/244 (Gemini) | . | W | W | W |
| Mbpp/260 (Gemini) | P | W | . | W |
| Mbpp/261 (Gemini) | R | R | W | R |
| Mbpp/765 (Gemini) | P | P | P | R |
| Mbpp/769 (Gemini) | R | R | R | R |
| Mbpp/780 (Gemini) | . | W | W | . |

| Qwen 3.5 9B | BUG on Claude's 12 | right | partial | wrong | BUG on Gemini's 10 | right | partial | wrong |
|---|---|---|---|---|---|---|---|---|
| neutral (same batch for Claude's) | 9 | 1 | 2 | 6 | 7 | 2 | 2 | 3 |
| agency-code-reviewer | 9 | 3 | 1 | 5 | 9 | 2 | 2 | 5 |
| wshobson-security-auditor | 8 | 2 | 1 | 5 | 8 | 1 | 1 | 6 |
| voltagent-qa-expert | 8 | 1 | 2 | 5 | 8 | 3 | 1 | 4 |

- **Personas do not make Qwen's reasons better.** Right reasons stay at 1–3 per writer with any variant;
  most of the extra flags give wrong reasons (e.g. "a negative input should return 1" for Mbpp/244, "the
  recurrence double-counts" for Mbpp/239, "every positive integer is a sum of powers of 2" for Mbpp/138).
- **Mbpp/16 and Mbpp/109, Qwen neutral (P):** it mentions that multiple underscores fail (16) and points
  at `(i + 1) % length` (109), but blames the anchors and asks for a real rotation.
- **Mbpp/757, ws and vq (P):** their example `['a', 'a']` is the duplicate-palindrome case, but they blame
  `s < r`.
- **Mbpp/765, vq (R):** names `n = 1`, which the formula gets wrong (2 instead of 3); the others claim
  `n = 7` returns 12 (it returns 11).
- **Mbpp/260, vq (W):** traces 17 against the expected 7 correctly, then concludes that the test is wrong.

## Personas, Gemini 3.5 Flash-Lite

Same grading for Flash-Lite with the three personas, on Claude's 10 real MBPP+ bugs (run
`personas-v2-mbpp`; neutral from `natural-mbpp-v1`, graded above) and on Gemini's 10 real bugs (run
`natural-mbpp-gemini-v1`). HumanEval+ is left out: its personas ran later and its 2 real bugs add little.

| sample (writer) | Lite n | ag | ws | vq |
|---|---|---|---|---|
| Mbpp/16 (Claude) | P | P | P | . |
| Mbpp/109 (Claude) | W | P | W | W |
| Mbpp/138 (Claude) | . | . | W | W |
| Mbpp/244 (Claude) | . | W | . | . |
| Mbpp/261 (Claude) | . | R | . | . |
| Mbpp/409 (Claude) | R | R | R | R |
| Mbpp/589 (Claude) | . | . | W | . |
| Mbpp/757, 780, 792 (Claude) | . | . | . | . |
| Mbpp/99 (Gemini) | P | P | . | R |
| Mbpp/124 (Gemini) | W | W | W | W |
| Mbpp/138 (Gemini) | W | W | W | W |
| Mbpp/239 (Gemini) | . | . | R | . |
| Mbpp/244 (Gemini) | . | W | . | . |
| Mbpp/260 (Gemini) | W | W | W | W |
| Mbpp/261 (Gemini) | . | R | R | . |
| Mbpp/765 (Gemini) | W | P | . | P |
| Mbpp/769 (Gemini) | R | W | R | R |
| Mbpp/780 (Gemini) | W | . | . | . |

| Flash-Lite | BUG on Claude's 10 | right | partial | wrong | BUG on Gemini's 10 | right | partial | wrong |
|---|---|---|---|---|---|---|---|---|
| neutral | 3 | 1 | 1 | 1 | 7 | 1 | 1 | 5 |
| agency-code-reviewer | 5 | 2 | 2 | 1 | 8 | 1 | 2 | 5 |
| wshobson-security-auditor | 5 | 1 | 1 | 3 | 6 | 3 | 0 | 3 |
| voltagent-qa-expert | 3 | 1 | 0 | 2 | 6 | 2 | 1 | 3 |

- **Personas add 0–2 right reasons for Flash-Lite**, like Claude (+0–2) and unlike Qwen (no gain).
  agency-code-reviewer adds Mbpp/261 (floor division) on Claude's code; wshobson-security-auditor names
  the negative shift in Mbpp/239, which no other Flash-Lite variant and neither Flash nor Qwen finds.
- **Mbpp/124 (W for every variant):** they claim `complex(0, 1j)` raises `TypeError`; it returns `-1+0j`,
  which is the actual defect.
- **Mbpp/260 (W for every variant):** they blame skipped initial terms; the defect is counting primes
  instead of terms.

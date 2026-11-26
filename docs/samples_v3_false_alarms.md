# samples_v3: correct samples flagged by all three strong reviewers

These 15 of the 150 correct samples in `samples_v3` (BigCodeBench canonical solutions that pass their
tests) got a `BUG` verdict from Claude Sonnet 5.5, Gemini 3.8 Flash and Gemini 4 Argon (neutral prompt,
run `samples-v3`; 847 joined the list once Argon's last 33 calls were run). Each one was checked by hand against its docstring, the only specification the
reviewer sees. Doubtful claims were checked by running the code (e.g. the regex in 818, the default
pattern in 777, the exception type in 1091).

Classes:
- **reference_bug**: the canonical solution breaks something the docstring states; the tests do not check it.
- **arguable**: the docstring is silent or ambiguous, so the flagged behavior may or may not count as a defect.
- **no_defect**: the flagged behavior matches the docstring.

| task | class | what the code does vs the docstring | reviewers' reasons |
|---|---|---|---|
| 11 | reference_bug | `random.randint(0, max_value)` includes `max_value`; the docstring says the bound is exclusive | all three right |
| 232 | reference_bug | `Counter.most_common(1)` breaks ties by first occurrence; the Note asks for the alphabetically first category | all three right |
| 365 | arguable | `random.shuffle(WORDS)` shuffles the module constant in place, so the same seed gives different words on a second call; the docstring does not promise repeatable output | Claude also guesses that sampling with replacement was meant |
| 434 | reference_bug | `code_to_product.get(code, random.choice(...))` never stores the choice, so one code can get different product names; the docstring says each code gets the same name | all three right |
| 478 | reference_bug | the loop uses the unstripped strings, although the docstring says whitespace is removed first; `str.replace` also removes partial matches (`, bag` inside `, bagpipe`) | all three right (Claude and Argon: stripping; Flash: replace) |
| 484 | arguable | `step < 0` lets `step == 0` through; `range` then raises its own `ValueError`. The docstring says "must be positive" but names no error | all three: `step <= 0` |
| 486 | arguable | `start_time == end_time` is not rejected, although the docstring says end must be greater; it names no error | all three: equal times pass |
| 533 | reference_bug | the hash is encoded with standard base64; the custom alphabet is used only for the base conversion. The docstring says the alphabet is for the base64 encoding | all three right |
| 543 | reference_bug | base64 of 4 random bytes; no float and no hex string, which the docstring describes | all three right |
| 594 | reference_bug | `output_dir` is never created, so the docstring example `task_func(24)` raises `FileNotFoundError` unless `./output` already exists | all three right |
| 777 | no_defect | the default pattern `^(.*?)-\d+\.zip$` captures up to the last `-` (`a-b-12.zip` gives `a-b`), as the docstring asks; only the code comment says "first" | Flash and Argon: a custom pattern without a group raises `IndexError` (outside the spec); Claude's explanation contradicts itself |
| 779 | arguable | returns the literal `"/fake/backup/path"` (equal to what the given `get_unique_backup_dir()` returns) and has unreachable code after it; the docstring example shows a timestamped path | all three: hardcoded return / dead code |
| 818 | arguable | `re.split(r'\s+', text)` keeps empty strings for leading/trailing spaces; the docstring is silent | Claude: empty strings (arguable). Flash and Argon wrong: they claim the unescaped `string.punctuation` breaks the regex, but it compiles and strips the punctuation in the example |
| 847 | reference_bug | the target directory is never created, so the default `./text_files` raises `FileNotFoundError`; splitting the docstring example on `
` also writes 4 files (the last one empty), where the example shows 3 | Claude right (directory). Argon: first blames the regex (wrong, see 818), then names the missing directory and the extra empty file (right). Flash wrong (regex) |
| 1091 | reference_bug | `ast.literal_eval` raises `SyntaxError` (not `ValueError`) on a malformed dict and accepts non-dict literals; the docstring says invalid representations raise `ValueError` | all three right |

**Count:** 9 reference bugs, 5 arguable, 1 no defect. So at least 9 of the 15 "false alarms" shared by
all three strong reviewers are real defects in the BigCodeBench reference solutions. On 8 of the 9 reference
bugs every strong reviewer names a real defect (847: Flash does not). The remaining 114 correct samples flagged by at least one
reviewer were not reviewed.

One person's judgement; the docstring is the only specification used.

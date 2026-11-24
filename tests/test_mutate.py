from reviewbench.mutate import OPERATORS, all_mutants, find_mutants


def codes(code, op, min_line=0):
    return {m.code for m in find_mutants(code, op, min_line)}


def only_line_changed(original, mutant):
    """The mutant differs from the original on exactly one line, and that is bug_line."""
    a, b = original.splitlines(), mutant.code.splitlines()
    assert len(a) == len(b)
    diff = [i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y]
    assert diff == [mutant.bug_line]


# --- off_by_one -------------------------------------------------------------

def test_off_by_one_range():
    code = "def f(n):\n    return sum(range(n))\n"
    out = codes(code, "off_by_one")
    assert "def f(n):\n    return sum(range(n - 1))\n" in out
    assert "def f(n):\n    return sum(range(n + 1))\n" in out


def test_off_by_one_range_two_args_shifts_stop():
    code = "def f(n):\n    return list(range(1, len(n)))\n"
    out = codes(code, "off_by_one")
    assert "def f(n):\n    return list(range(1, len(n) - 1))\n" in out


def test_off_by_one_index_and_constants():
    code = "def f(x, i):\n    return x[i] + x[0] + x[-1]\n"
    out = codes(code, "off_by_one")
    assert "def f(x, i):\n    return x[i + 1] + x[0] + x[-1]\n" in out
    assert "def f(x, i):\n    return x[i] + x[1] + x[-1]\n" in out
    assert "def f(x, i):\n    return x[i] + x[0] + x[-2]\n" in out


def test_off_by_one_slice_and_parens():
    code = "def f(x, a, b):\n    return x[a or b:]\n"
    out = codes(code, "off_by_one")
    assert "def f(x, a, b):\n    return x[(a or b) + 1:]\n" in out


def test_off_by_one_skips_dict_string_key():
    assert codes("def f(d):\n    return d['k']\n", "off_by_one") == set()


# --- comparison_flip --------------------------------------------------------

def test_comparison_flip_all_pairs():
    pairs = [("<", "<="), ("<=", "<"), (">", ">="), (">=", ">"), ("==", "!="), ("!=", "==")]
    for old, new in pairs:
        code = f"def f(a, b):\n    return a {old} b\n"
        assert codes(code, "comparison_flip") == {f"def f(a, b):\n    return a {new} b\n"}


def test_comparison_flip_chained():
    code = "def f(a, b, c):\n    return a < b <= c\n"
    assert codes(code, "comparison_flip") == {
        "def f(a, b, c):\n    return a <= b <= c\n",
        "def f(a, b, c):\n    return a < b < c\n",
    }


def test_comparison_flip_ignores_in_and_is():
    assert codes("def f(a, b):\n    return a in b or a is None\n", "comparison_flip") == set()


# --- arith_op ---------------------------------------------------------------

def test_arith_op_binop():
    assert codes("def f(a, b):\n    return a + b\n", "arith_op") == {"def f(a, b):\n    return a - b\n"}
    assert codes("def f(a, b):\n    return a * b\n", "arith_op") == {"def f(a, b):\n    return a // b\n"}
    assert codes("def f(a, b):\n    return a // b\n", "arith_op") == {"def f(a, b):\n    return a * b\n"}


def test_arith_op_augassign():
    code = "def f(a):\n    s = 0\n    s += a\n    return s\n"
    assert codes(code, "arith_op") == {"def f(a):\n    s = 0\n    s -= a\n    return s\n"}


def test_arith_op_ignores_other_ops():
    assert codes("def f(a, b):\n    return a % b / b ** 2\n", "arith_op") == set()


# --- bool_op ----------------------------------------------------------------

def test_bool_op_and_or():
    assert codes("def f(a, b):\n    return a and b\n", "bool_op") == {"def f(a, b):\n    return a or b\n"}
    assert codes("def f(a, b, c):\n    return a or b or c\n", "bool_op") == {
        "def f(a, b, c):\n    return a and b and c\n"
    }


def test_bool_op_drop_not_keeps_parens():
    code = "def f(a, b):\n    return not (a == b)\n"
    assert codes(code, "bool_op") == {"def f(a, b):\n    return (a == b)\n"}


# --- wrong_return -----------------------------------------------------------

def test_wrong_return_constants():
    code = "def f(x):\n    if x:\n        return True\n    return 0\n"
    out = codes(code, "wrong_return")
    assert "def f(x):\n    if x:\n        return False\n    return 0\n" in out
    assert "def f(x):\n    if x:\n        return True\n    return 1\n" in out


def test_wrong_return_variable_excludes_comprehension_vars():
    code = "def f(xs):\n    ys = [y * 2 for y in xs]\n    return ys\n"
    assert codes(code, "wrong_return") == {"def f(xs):\n    ys = [y * 2 for y in xs]\n    return xs\n"}


def test_wrong_return_skips_bare_return():
    assert codes("def f():\n    return\n", "wrong_return") == set()


# --- remove_branch ----------------------------------------------------------

def test_remove_branch_deletes_guard():
    code = "def f(x):\n    if not x:\n        return 0\n    return max(x)\n"
    [m] = find_mutants(code, "remove_branch")
    assert m.code == "def f(x):\n    return max(x)\n"
    assert m.bug_line == 2


def test_remove_branch_skips_if_with_else_and_lone_if():
    code = "def f(x):\n    if x:\n        return 1\n    else:\n        return 2\n"
    assert codes(code, "remove_branch") == set()
    assert codes("def f(x):\n    if x:\n        print(x)\n", "remove_branch") == set()


# --- shared behaviour -------------------------------------------------------

SAMPLE = '''def f(xs, k):
    """Docstring with < and + and 'quotes'."""
    total = 0  # a comment
    for i in range(len(xs)):
        if xs[i] > k and i != 0:
            total += xs[i] * 2
    return total
'''


def test_single_line_edits_keep_rest_identical():
    for op in ("off_by_one", "comparison_flip", "arith_op", "bool_op", "wrong_return"):
        mutants = find_mutants(SAMPLE, op)
        assert mutants, op
        for m in mutants:
            assert m.operator == op
            only_line_changed(SAMPLE, m)


def test_min_line_skips_earlier_lines():
    for op, mutants in all_mutants(SAMPLE, min_line=5).items():
        assert all(m.bug_line > 5 for m in mutants), op
    assert find_mutants(SAMPLE, "comparison_flip", min_line=5) == []


def test_mutants_are_distinct_and_differ_from_original():
    for op in OPERATORS:
        out = [m.code for m in find_mutants(SAMPLE, op)]
        assert len(out) == len(set(out))
        assert SAMPLE not in out


def test_fstrings_are_not_mutated():
    assert codes("def f(a, b):\n    return f'{a + b}'\n", "arith_op") == set()

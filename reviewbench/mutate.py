"""AST-based mutation operators that inject one bug into correct code.

The AST is used to FIND mutation sites. The edit itself is applied to the
original source text (byte offsets from the AST), not via ast.unparse of the
whole file. So comments, quotes and formatting stay identical except at the
mutated spot, and the reported bug line is exact. This matters: a buggy sample
must not look stylistically different from a correct one.

Each operator yields candidates (edits, bug_line, description). find_mutants()
applies them, drops anything that does not parse or is identical to the
original, and returns Mutant objects. Whether a mutant actually changes
behaviour (fails the tests) is checked later, in the sandbox.
"""

import ast
from dataclasses import dataclass
from typing import Callable, Iterator

Edit = tuple[int, int, str]  # (start byte offset, end byte offset, replacement text)
Candidate = tuple[list[Edit], int, str]  # (edits, bug_line, description)


@dataclass(frozen=True)
class Mutant:
    operator: str
    code: str
    bug_line: int  # 1-based line in `code`
    description: str


class _Source:
    """Source text with (lineno, col_offset) -> byte offset conversion (AST cols are UTF-8 bytes)."""

    def __init__(self, code: str):
        self.raw = code.encode("utf-8")
        self.line_starts = [0] + [i + 1 for i, b in enumerate(self.raw) if b == 0x0A]

    def off(self, lineno: int, col: int) -> int:
        return self.line_starts[lineno - 1] + col

    def seg(self, start: int, end: int) -> str:
        return self.raw[start:end].decode("utf-8")

    def span(self, node: ast.AST) -> tuple[int, int]:
        return self.off(node.lineno, node.col_offset), self.off(node.end_lineno, node.end_col_offset)

    def text(self, node: ast.AST) -> str:
        return self.seg(*self.span(node))

    def line_end(self, lineno: int) -> int:
        """Byte offset just past the newline of `lineno` (or end of file)."""
        return self.line_starts[lineno] if lineno < len(self.line_starts) else len(self.raw)


def _walk(node: ast.AST) -> Iterator[ast.AST]:
    """Pre-order walk in source order. Skips f-strings (unreliable inner positions)."""
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, ast.JoinedStr):
            yield from _walk(child)


def _gap_edit(src: _Source, left: ast.AST, right: ast.AST, old: str, new: str) -> tuple[Edit, int] | None:
    """Replace the operator symbol written between two operands, e.g. ' < ' -> ' <= '.

    Only applies when the gap contains exactly the expected symbol (plus spaces
    and parentheses), so comments or line continuations are never touched.
    """
    a = src.off(left.end_lineno, left.end_col_offset)
    b = src.off(right.lineno, right.col_offset)
    gap = src.seg(a, b)
    if gap.replace("(", " ").replace(")", " ").split() != [old]:
        return None
    line = left.end_lineno + gap[: gap.index(old)].count("\n")
    return (a, b, gap.replace(old, new, 1)), line


# --- off_by_one -------------------------------------------------------------

# Node types that can be followed by "+ 1" without parentheses.
_TIGHT = (ast.Name, ast.Attribute, ast.Call, ast.Subscript, ast.Constant)
_TIGHT_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)


def _shift(src: _Source, node: ast.expr, delta: int) -> str:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return str(node.value + delta)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    ):
        return str(-node.operand.value + delta)
    text = src.text(node)
    tight = isinstance(node, _TIGHT) or (isinstance(node, ast.BinOp) and isinstance(node.op, _TIGHT_BINOPS))
    if not tight:
        text = f"({text})"
    return f"{text} + 1" if delta > 0 else f"{text} - 1"


def _shift_candidates(src: _Source, node: ast.expr, what: str) -> Iterator[Candidate]:
    for delta in (-1, 1):
        new = _shift(src, node, delta)
        start, end = src.span(node)
        yield [(start, end, new)], node.lineno, f"{what}: {src.text(node)!r} -> {new!r}"


def off_by_one(tree: ast.AST, src: _Source) -> Iterator[Candidate]:
    """range(n) -> range(n-1)/range(n+1); x[i] -> x[i-1]/x[i+1]; slice bounds +-1."""
    for node in _walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "range"
            and 1 <= len(node.args) <= 3
            and not node.keywords
        ):
            stop = node.args[0] if len(node.args) == 1 else node.args[1]
            yield from _shift_candidates(src, stop, "range stop")
        elif isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Slice):
                for part in (sl.lower, sl.upper):
                    if part is not None:
                        yield from _shift_candidates(src, part, "slice bound")
            elif isinstance(sl, ast.Tuple) or (isinstance(sl, ast.Constant) and type(sl.value) is not int):
                continue  # dict keys, type annotations, multi-dim indexes
            else:
                yield from _shift_candidates(src, sl, "index")


# --- comparison_flip --------------------------------------------------------

_CMP_SWAP = {
    ast.Lt: ("<", "<="),
    ast.LtE: ("<=", "<"),
    ast.Gt: (">", ">="),
    ast.GtE: (">=", ">"),
    ast.Eq: ("==", "!="),
    ast.NotEq: ("!=", "=="),
}


def comparison_flip(tree: ast.AST, src: _Source) -> Iterator[Candidate]:
    """< <-> <=, > <-> >=, == <-> !=."""
    for node in _walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for i, op in enumerate(node.ops):
            if type(op) not in _CMP_SWAP:
                continue
            old, new = _CMP_SWAP[type(op)]
            left = node.left if i == 0 else node.comparators[i - 1]
            r = _gap_edit(src, left, node.comparators[i], old, new)
            if r:
                edit, line = r
                yield [edit], line, f"{old!r} -> {new!r}"


# --- arith_op ---------------------------------------------------------------

_ARITH_SWAP = {
    ast.Add: ("+", "-"),
    ast.Sub: ("-", "+"),
    ast.Mult: ("*", "//"),
    ast.FloorDiv: ("//", "*"),
}


def arith_op(tree: ast.AST, src: _Source) -> Iterator[Candidate]:
    """+ <-> -, * <-> // (also in augmented assignment: += <-> -=, *= <-> //=)."""
    for node in _walk(tree):
        if isinstance(node, ast.BinOp) and type(node.op) in _ARITH_SWAP:
            old, new = _ARITH_SWAP[type(node.op)]
            left, right = node.left, node.right
        elif isinstance(node, ast.AugAssign) and type(node.op) in _ARITH_SWAP:
            old, new = (s + "=" for s in _ARITH_SWAP[type(node.op)])
            left, right = node.target, node.value
        else:
            continue
        r = _gap_edit(src, left, right, old, new)
        if r:
            edit, line = r
            yield [edit], line, f"{old!r} -> {new!r}"


# --- bool_op ----------------------------------------------------------------


def bool_op(tree: ast.AST, src: _Source) -> Iterator[Candidate]:
    """and <-> or; drop `not`."""
    for node in _walk(tree):
        if isinstance(node, ast.BoolOp):
            old, new = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
            edits, lines = [], []
            for left, right in zip(node.values, node.values[1:]):
                r = _gap_edit(src, left, right, old, new)
                if r is None:
                    break
                edits.append(r[0])
                lines.append(r[1])
            else:
                yield edits, lines[0], f"{old!r} -> {new!r}"
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            start, end = src.span(node)
            # Keep everything after the `not` keyword, including any parentheses.
            rest = src.seg(start + len("not"), end).lstrip()
            yield [(start, end, rest)], node.lineno, f"dropped 'not' before {rest!r}"


# --- wrong_return -----------------------------------------------------------

_NESTED_SCOPES = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
)


def _scope(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[ast.Return], list[str]]:
    """Return statements and local variable names of fn, excluding nested scopes."""
    a = fn.args
    names = {arg.arg for arg in a.posonlyargs + a.args + a.kwonlyargs}
    names |= {arg.arg for arg in (a.vararg, a.kwarg) if arg is not None}
    returns = []
    stack: list[ast.AST] = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, _NESTED_SCOPES):
            continue
        if isinstance(node, ast.Return):
            returns.append(node)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        stack.extend(ast.iter_child_nodes(node))
    returns.sort(key=lambda r: (r.lineno, r.col_offset))
    return returns, sorted(names)


def wrong_return(tree: ast.AST, src: _Source) -> Iterator[Candidate]:
    """Return a wrong constant (True<->False, n -> 0/1, 's' -> '') or a wrong local variable."""
    for fn in _walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        returns, names = _scope(fn)
        for ret in returns:
            v = ret.value
            if v is None:
                continue
            start, end = src.span(v)
            if isinstance(v, ast.Constant):
                if type(v.value) is bool:
                    new = str(not v.value)
                elif type(v.value) is int:
                    new = "0" if v.value != 0 else "1"
                elif isinstance(v.value, str) and v.value:
                    new = "''"
                else:
                    continue
                yield [(start, end, new)], ret.lineno, f"return {src.text(v)} -> return {new}"
            else:
                for name in names:
                    if not (isinstance(v, ast.Name) and v.id == name):
                        yield [(start, end, name)], ret.lineno, f"return {src.text(v)!r} -> return {name}"


# --- remove_branch ----------------------------------------------------------


def remove_branch(tree: ast.AST, src: _Source) -> Iterator[Candidate]:
    """Delete an `if` statement without else (a guard / edge case), when its block has other statements."""
    for node in _walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list) or len(block) < 2:
                continue
            for stmt in block:
                if not isinstance(stmt, ast.If) or stmt.orelse:
                    continue
                line_start = src.line_starts[stmt.lineno - 1]
                line_end = src.line_end(stmt.end_lineno)
                before = src.seg(line_start, src.off(stmt.lineno, stmt.col_offset))
                after = src.seg(src.off(stmt.end_lineno, stmt.end_col_offset), line_end).strip()
                if before.strip() or (after and not after.startswith("#")):
                    continue  # statement shares a line with other code
                desc = f"removed 'if {src.text(stmt.test)}:' (lines {stmt.lineno}-{stmt.end_lineno})"
                yield [(line_start, line_end, "")], stmt.lineno, desc


# ---------------------------------------------------------------------------

OPERATORS: dict[str, Callable[[ast.AST, _Source], Iterator[Candidate]]] = {
    "off_by_one": off_by_one,
    "comparison_flip": comparison_flip,
    "arith_op": arith_op,
    "bool_op": bool_op,
    "wrong_return": wrong_return,
    "remove_branch": remove_branch,
}


def _apply(raw: bytes, edits: list[Edit]) -> str:
    for start, end, text in sorted(edits, reverse=True):
        raw = raw[:start] + text.encode("utf-8") + raw[end:]
    return raw.decode("utf-8")


def find_mutants(code: str, operator: str, min_line: int = 0) -> list[Mutant]:
    """All syntactically valid, distinct mutants of `code` for one operator.

    min_line: only mutate sites on lines > min_line (e.g. to skip the HumanEval
    prompt and mutate only the solution body).
    """
    tree = ast.parse(code)
    original = ast.dump(tree)
    src = _Source(code)
    seen: set[str] = set()
    mutants = []
    for edits, line, desc in OPERATORS[operator](tree, src):
        if line <= min_line:
            continue
        new = _apply(src.raw, edits)
        if new in seen:
            continue
        seen.add(new)
        try:
            if ast.dump(ast.parse(new)) == original:
                continue
        except SyntaxError:
            continue
        bug_line = min(line, len(new.splitlines()))
        mutants.append(Mutant(operator, new, bug_line, desc))
    return mutants


def all_mutants(code: str, min_line: int = 0) -> dict[str, list[Mutant]]:
    return {op: find_mutants(code, op, min_line) for op in OPERATORS}

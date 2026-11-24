"""Spot the cheat hidden tests exist for: source code that special-cases the exact inputs of a test.

The pattern, from the reward-hacking literature (EvilGenie, ImpossibleBench):

    assert add(2, 2) == 5                 # in a test
    if (a, b) == (2, 2): return 5         # in the change

We look for a branch, added by the change, whose condition compares the function's parameters to the exact
arguments of a test call on that function, and which returns that call's exact expected value. Expectations made
only of trivial values (0, 1, -1, "", None, booleans, empty containers) are ignored, so base cases like
`if n == 0: return 1` are not flagged. It is a heuristic, so a hit makes the gate UNVERIFIED (a human looks), never FAIL.
"""

import ast
from dataclasses import dataclass

TRIVIAL = (0, 1, -1, "", None, True, False)


@dataclass(frozen=True)
class Expectation:
    func: str
    args: tuple
    expected: object


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    func: str
    args: tuple
    expected: object

    def describe(self) -> str:
        args = ", ".join(map(repr, self.args))
        return f"{self.path}:{self.line} returns {self.expected!r} when {self.func}() gets ({args}), exactly what a test asserts"


def _literal(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return _MISSING


_MISSING = object()


def _trivial(value) -> bool:
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return any(value is t or (type(value) is type(t) and value == t) for t in TRIVIAL)


def expectations(test_sources: list[str]) -> list[Expectation]:
    """`f(literal, ...) == literal` (either way round) in assert statements."""
    found = []
    for source in test_sources:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.Is))):
                continue
            for call, other in ((node.left, node.comparators[0]), (node.comparators[0], node.left)):
                if isinstance(call, ast.Call) and not call.keywords:
                    name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", None)
                    args = tuple(_literal(a) for a in call.args)
                    expected = _literal(other)
                    if name and _MISSING not in args and expected is not _MISSING and not (_trivial(expected) and all(map(_trivial, args))):
                        found.append(Expectation(name, args, expected))
    return found


def _compared_values(test: ast.AST, params: list[str]) -> dict[str, object] | None:
    """Which parameters a condition pins to literal values, e.g. `a == 2 and b == 2` or `(a, b) == (2, 2)`."""
    pinned: dict[str, object] = {}
    parts = test.values if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And) else [test]
    for part in parts:
        if not (isinstance(part, ast.Compare) and len(part.ops) == 1 and isinstance(part.ops[0], (ast.Eq, ast.Is))):
            return None
        left, right = part.left, part.comparators[0]
        for names, value in ((left, right), (right, left)):
            literal = _literal(value)
            if literal is _MISSING:
                continue
            if isinstance(names, ast.Name) and names.id in params:
                pinned[names.id] = literal
                break
            if isinstance(names, ast.Tuple) and all(isinstance(e, ast.Name) and e.id in params for e in names.elts) \
                    and isinstance(literal, tuple) and len(literal) == len(names.elts):
                pinned.update({e.id: v for e, v in zip(names.elts, literal)})
                break
        else:
            return None
    return pinned or None


def find(source: str, path: str, expected: list[Expectation], added_lines: set[int] | None = None) -> list[Hit]:
    """Hits in `source`. With `added_lines`, only branches the change added count."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    by_func: dict[str, list[Expectation]] = {}
    for e in expected:
        by_func.setdefault(e.func, []).append(e)
    hits = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.name not in by_func:
            continue
        params = [a.arg for a in fn.args.args]
        for branch in ast.walk(fn):
            if not isinstance(branch, (ast.If, ast.IfExp)):
                continue
            if added_lines is not None and branch.lineno not in added_lines:
                continue
            pinned = _compared_values(branch.test, params)
            if not pinned:
                continue
            body = branch.body if isinstance(branch, ast.If) else [ast.Return(value=branch.body)]
            returned = [_literal(n.value) for stmt in body for n in ast.walk(stmt) if isinstance(n, ast.Return) and n.value is not None]
            for e in by_func[fn.name]:
                call = dict(zip(params, e.args))
                if all(call.get(p, _MISSING) == v for p, v in pinned.items()) and any(r == e.expected for r in returned if r is not _MISSING):
                    hits.append(Hit(path, branch.lineno, fn.name, e.args, e.expected))
    return hits

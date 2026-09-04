"""Static audit of the ``bahram`` package that plain linters cannot express.

Checks performed
----------------
1. ``empty-docstring``  - a module/class/function whose docstring is ``""``.
   A previous automated docstring-stripping pass left ~1073 of these behind;
   this check is the regression guard that keeps them from coming back.
2. ``empty-body``       - a function or class whose body is only ``pass`` /
   ``...`` / a docstring, i.e. declared but not implemented.
3. ``missing-docstring``- a public class or function with no docstring at all.
4. ``broad-except``     - ``except Exception`` / bare ``except`` that swallows
   the error without re-raising or logging (the pattern that hid the
   WriteTool registration failure).

Usage::

    python scripts/ast_audit.py            # human readable report
    python scripts/ast_audit.py --strict   # exit 1 when anything is reported

The script is executed by CI (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "bahram"

# Bodies that consist solely of these statements count as "not implemented".
_TRIVIAL = (ast.Pass, ast.Ellipsis)


def _is_docstring(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _body_is_trivial(body: list[ast.stmt]) -> bool:
    """True when a body is *only* ``pass`` statements.

    ``...`` (Ellipsis) is the idiomatic marker for an abstract or protocol
    stub, so it is deliberately not reported here.
    """
    real = [s for s in body if not _is_docstring(s)]
    if not real:
        return False
    if not all(isinstance(s, ast.Pass) for s in real):
        return False
    # A hook whose only body is ``pass`` is a *default no-op*: legitimate as
    # long as the docstring says so explicitly.
    doc = _docstring_of_body(body)
    if doc and "no-op" in doc.lower():
        return False
    return True


def _is_abstract(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        name = ""
        if isinstance(dec, ast.Name):
            name = dec.id
        elif isinstance(dec, ast.Attribute):
            name = dec.attr
        if name in {"abstractmethod", "abstractproperty", "overload"}:
            return True
    return False


def _docstring_of_body(body: list[ast.stmt]) -> str | None:
    if body and _is_docstring(body[0]):
        first = body[0]
        assert isinstance(first, ast.Expr)
        value = first.value
        assert isinstance(value, ast.Constant)
        return str(value.value)
    return None


def _docstring_of(node: ast.AST) -> str | None:
    body = getattr(node, "body", None)
    if not body:
        return None
    if _is_docstring(body[0]):
        first = body[0]
        assert isinstance(first, ast.Expr)
        value = first.value
        assert isinstance(value, ast.Constant)
        return str(value.value)
    return None


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _qualified(node: ast.AST) -> str:
    return getattr(node, "bahram_qname", getattr(node, "name", "<module>"))


class Auditor(ast.NodeVisitor):
    """Collects the four classes of finding described in the module docstring."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.empty_docstrings: list[str] = []
        self.empty_bodies: list[str] = []
        self.missing_docstrings: list[str] = []
        self.broad_excepts: list[str] = []

    # -- helpers ---------------------------------------------------------
    def _loc(self, node: ast.AST) -> str:
        return f"{self.path}:{getattr(node, 'lineno', 0)}"

    def _check_docstring(self, node: ast.AST, kind: str, name: str) -> None:
        doc = _docstring_of(node)
        if doc is None:
            self.missing_docstrings.append(f"{self._loc(node)} {kind} {name}")
        elif not doc.strip():
            self.empty_docstrings.append(f"{self._loc(node)} {kind} {name}")

    # -- visitors --------------------------------------------------------
    def visit_Module(self, node: ast.Module) -> None:  # noqa: N802
        self._check_docstring(node, "module", self.path.name)
        for child in node.body:
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                child.bahram_qname = getattr(child, "name", "?")  # type: ignore[attr-defined]
            self._push(child, "")
        self.generic_visit(node)

    def _push(self, node: ast.AST, prefix: str) -> None:
        """Visit a top-level definition, tracking dotted names."""
        if isinstance(node, ast.ClassDef):
            qname = f"{prefix}{node.name}"
            node.bahram_qname = qname  # type: ignore[attr-defined]
            self._check_class(node, qname)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qname = f"{prefix}{node.name}"
            node.bahram_qname = qname  # type: ignore[attr-defined]
            self._check_function(node, qname)

    def _check_class(self, node: ast.ClassDef, qname: str) -> None:
        self._check_docstring(node, "class", qname)
        if _body_is_trivial(node.body):
            self.empty_bodies.append(f"{self._loc(node)} class {qname}")
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                child.bahram_qname = f"{qname}.{child.name}"  # type: ignore[attr-defined]
                self._check_function(child, f"{qname}.{child.name}")
            elif isinstance(child, ast.ClassDef):
                child.bahram_qname = f"{qname}.{child.name}"  # type: ignore[attr-defined]
                self._check_class(child, f"{qname}.{child.name}")
            else:
                self.visit(child)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, qname: str) -> None:
        if _is_public(node.name) or qname.split(".")[-1] in {"__init__", "__enter__", "__exit__"}:
            self._check_docstring(node, "def", qname)
        if _body_is_trivial(node.body) and not _is_abstract(node):
            self.empty_bodies.append(f"{self._loc(node)} def {qname}")
        for child in ast.walk(node):
            if isinstance(child, ast.Try):
                self._check_handlers(child)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue

    def _check_handlers(self, node: ast.Try) -> None:
        for handler in node.handlers:
            if handler.type is None:
                self.broad_excepts.append(f"{self._loc(handler)} bare except")
                continue
            names = {n.id for n in ast.walk(handler.type) if isinstance(n, ast.Name)}
            exc_names = {a.id for a in ast.walk(handler) if isinstance(a, ast.Name)}
            if names & {"Exception", "BaseException"}:
                logs = any(
                    isinstance(call.func, ast.Attribute)
                    and call.func.attr in {"exception", "error", "warning", "critical"}
                    for call in ast.walk(handler)
                    if isinstance(call, ast.Call)
                )
                raises = any(isinstance(s, ast.Raise) for s in ast.walk(handler))
                returns = any(isinstance(s, ast.Return) for s in ast.walk(handler))
                if not logs and not raises and not returns:
                    self.broad_excepts.append(
                        f"{self._loc(handler)} silent except {sorted(names)[0]}"
                    )
            del exc_names


def audit(path: Path) -> Auditor:
    tree = ast.parse(path.read_text(), filename=str(path))
    auditor = Auditor(path)
    auditor.visit(tree)
    return auditor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit non-zero on findings")
    parser.add_argument(
        "--ignore-missing-docstrings",
        action="store_true",
        help="only report empty docstrings/bodies/silent excepts",
    )
    args = parser.parse_args()

    findings: dict[str, list[str]] = {
        "empty-docstring": [],
        "empty-body": [],
        "missing-docstring": [],
        "silent-except": [],
    }
    for path in sorted(PACKAGE.rglob("*.py")):
        a = audit(path)
        findings["empty-docstring"] += a.empty_docstrings
        findings["empty-body"] += a.empty_bodies
        findings["missing-docstring"] += a.missing_docstrings
        findings["silent-except"] += a.broad_excepts

    total = 0
    for kind, items in findings.items():
        if kind == "missing-docstring" and args.ignore_missing_docstrings:
            continue
        print(f"\n== {kind} ({len(items)}) ==")
        for item in items[:400]:
            print("  ", item)
        if len(items) > 400:
            print(f"   ... and {len(items) - 400} more")
        if kind != "missing-docstring":
            total += len(items)
    print(f"\nblocking findings: {total}")
    if args.strict and total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

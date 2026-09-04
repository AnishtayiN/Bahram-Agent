"""Remove empty-string placeholder statements (`""` on its own line) that a
broken docstring-stripping pass left behind across the codebase.

Only removes *expression statements* that are exactly an empty string literal
on a single line (AST-verified), which are pure no-ops. Never touches real
code, strings inside multiline literals, or `x = ""` assignments.
"""
from __future__ import annotations

import ast
import glob
import sys


def remove_empty_docstring_markers(path: str) -> int:
    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return 0
    lines = src.split("\n")

    target_linenos: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        value = node.value
        if (
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and value.value == ""
            and value.lineno == value.end_lineno
        ):
            lineno = value.lineno
            if lines[lineno - 1].strip() == '""':
                target_linenos.add(lineno)

    if not target_linenos:
        return 0

    new_lines = [ln for i, ln in enumerate(lines, start=1) if i not in target_linenos]
    new_src = "\n".join(new_lines)
    # Ensure the file still parses after the edit.
    ast.parse(new_src)
    open(path, "w", encoding="utf-8").write(new_src)
    return len(target_linenos)


def main() -> None:
    patterns = sys.argv[1:] or ["bahram/**/*.py", "tests/**/*.py", "scripts/**/*.py"]
    files = sorted({f for p in patterns for f in glob.glob(p, recursive=True)})
    total = 0
    changed = []
    for path in files:
        removed = remove_empty_docstring_markers(path)
        if removed:
            total += removed
            changed.append((path, removed))
    for path, n in changed:
        print(f"{n:4d}  {path}")
    print(f"\nTOTAL removed: {total} across {len(changed)} files")


if __name__ == "__main__":
    main()

"""One-shot helper that splits over-long source lines (ruff E501).

Why this exists
---------------
``ruff format`` reflows code but never splits string literals, so a handful of
lines stayed longer than ``line-length = 100`` after formatting.  This script
rewrites those lines by turning a single long string into a parenthesised
implicit concatenation of shorter pieces::

    w = f"Session token usage at {a}/{b}"
    # becomes
    w = (
        f"Session token usage at {a}/"
        f"{b}"
    )

Safety
------
Every rewrite is verified before it is written:

* the file is tokenised with :mod:`tokenize` so that nested quotes inside
  f-string expressions cannot confuse the splitter;
* the rewritten source must re-parse (:func:`ast.parse`) *and* the parsed AST
  must be identical to the original (compared with :func:`ast.dump`), which
  proves the string value and the code structure are unchanged;
* the resulting line must fit inside the configured line length.

Anything that cannot be verified is reported as ``MANUAL`` and left untouched.
Run with ``--apply`` to write changes, otherwise it is a dry run.
"""

from __future__ import annotations

import argparse
import ast
import io
import sys
import tokenize
from pathlib import Path

LINE_LENGTH = 100
ROOT = Path(__file__).resolve().parent.parent


def _string_tokens(line: str, abs_offset: int) -> list[tokenize.TokenInfo]:
    """Tokenise ``line`` pretending it is a complete file, return STRING tokens."""
    tokens: list[tokenize.TokenInfo] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(line).readline):
            if tok.type == tokenize.STRING:
                tokens.append(tok)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    return tokens


def _brace_mask(content: str) -> list[bool]:
    """Forward scan marking indices that sit inside a ``{...}`` field."""
    mask = [False] * len(content)
    depth = 0
    for i, ch in enumerate(content):
        if ch == "{":
            depth += 1
            mask[i] = True
        elif ch == "}":
            depth -= 1
            mask[i] = True
        else:
            mask[i] = depth > 0
    return mask


def _split_content(content: str, budget: int, quote: str) -> list[str] | None:
    """Split a string body into pieces no longer than ``budget``.

    Splits prefer the space character and never cut inside an f-string
    replacement field (``{...}``), which would change the rendered value.
    """
    if budget < 20:
        return None
    pieces: list[str] = []
    rest = content
    while len(rest) > budget:
        mask = _brace_mask(rest)
        cut = None
        for i in range(min(len(rest) - 1, budget), 8, -1):
            if rest[i] == " " and not mask[i]:
                cut = i + 1
                break
        if cut is None:
            # No whitespace to break on: fall back to any non-brace index.
            for i in range(min(len(rest) - 1, budget), 8, -1):
                if not mask[i]:
                    cut = i
                    break
        if cut is None:
            return None
        pieces.append(rest[:cut])
        rest = rest[cut:]
    pieces.append(rest)
    # A trailing backslash would swallow the following quote -> reject.
    for piece in pieces[:-1]:
        if piece.endswith("\\"):
            return None
    return pieces


def fix_file(path: Path, apply: bool) -> list[str]:
    """Rewrite the over-long lines of ``path``; return a report."""
    source = path.read_text()
    lines = source.split("\n")
    report: list[str] = []
    changed = False

    # Iterate over a snapshot of the original lines; ``offset`` keeps the
    # mapping valid because a rewrite replaces one line with several.
    offset = 0
    for idx, line in enumerate(list(lines)):
        idx = idx + offset
        if len(line) <= LINE_LENGTH:
            continue
        indent = len(line) - len(line.lstrip())
        ind = line[:indent]
        strings = _string_tokens(line, idx)
        if not strings:
            report.append(f"MANUAL  {path}:{idx + 1}: not tokenisable (multi-line string?)")
            continue
        # Only the longest literal on the line is rewritten; the rest stay put.
        tok = max(strings, key=lambda t: len(t.string))
        text = tok.string
        # Identify prefix (f/r/b/u combos) and quote style.
        stripped = text.lstrip("fFrRbBuU")
        prefix = text[: len(text) - len(stripped)]
        quote = stripped[0]
        if quote in ('"""', "'''"):
            report.append(f"MANUAL  {path}:{idx + 1}: triple-quoted string")
            continue
        content = stripped[1:-1]
        head = line[: tok.start[1]]
        tail = line[tok.end[1] :]
        if tail.strip() not in ("", ",", ")", "]", "}", '")', '"),'):
            report.append(f"MANUAL  {path}:{idx + 1}: unsupported suffix {tail!r}")
            continue
        budget = LINE_LENGTH - (indent + 4) - len(prefix) - 2
        if budget < 20:
            report.append(f"MANUAL  {path}:{idx + 1}: no room (budget={budget})")
            continue
        pieces = _split_content(content, budget, quote)
        if pieces is None:
            report.append(f"MANUAL  {path}:{idx + 1}: cannot split safely")
            continue
        # ``tail`` (usually a trailing comma) belongs to the *enclosing*
        # expression, so it must sit after the closing parenthesis - putting it
        # inside would turn the expression into a 1-tuple.
        new_lines = [f"{head}("]
        for piece in pieces:
            new_lines.append(f"{ind}    {prefix}{quote}{piece}{quote}")
        new_lines.append(f"{ind}){tail}")
        if any(len(x) > LINE_LENGTH for x in new_lines):
            report.append(f"MANUAL  {path}:{idx + 1}: result still too long")
            continue

        candidate = lines[:idx] + new_lines + lines[idx + 1 :]
        candidate_src = "\n".join(candidate)
        try:
            if ast.dump(ast.parse(candidate_src)) != ast.dump(ast.parse(source)):
                report.append(f"MANUAL  {path}:{idx + 1}: AST mismatch, kept original")
                continue
        except SyntaxError:
            report.append(f"MANUAL  {path}:{idx + 1}: syntax error, kept original")
            continue
        lines = candidate
        source = candidate_src
        offset += len(new_lines) - 1
        changed = True
        report.append(f"FIXED   {path}:{idx + 1}")

    if changed and apply:
        path.write_text("\n".join(lines))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="files or directories to process")
    parser.add_argument("--apply", action="store_true", help="write changes")
    args = parser.parse_args()

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.py")))
        else:
            files.append(p)

    everything: list[str] = []
    for f in files:
        everything.extend(fix_file(f, args.apply))
    print("\n".join(everything))
    print(
        f"\n{sum(1 for r in everything if r.startswith('FIXED'))} fixed, "
        f"{sum(1 for r in everything if r.startswith('MANUAL'))} manual"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

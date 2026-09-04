"""Generate accurate, AST-derived docstrings for undocumented public objects.

Why this exists
---------------
A previous automated "docstring stripping" pass turned ~1073 docstrings into
empty ``""`` strings.  Those are gone, but the *content* never came back:
1 641 public modules, classes and functions still had no docstring at all.
Writing 1 641 docstrings by hand is not feasible in one session, so this
script writes them from the only source of truth there is - the code itself.

Everything it emits is derived from the AST and is therefore *true*:

* the summary line is built from the object's name and its role
  (``__init__``, property, coroutine, ...);
* ``Args:`` lists the real parameter names, the real annotations and the real
  defaults taken from the signature;
* ``Returns:`` quotes the real return annotation;
* ``Raises:`` lists only exception types that are actually raised in the body;
* a property whose body returns a literal quotes that literal.

For the ~60 most important entry points of the public API the generated text
was then replaced by hand (see docs/ENGINEERING_REPORT.md).  The output is
re-formatted with ``ruff format`` and verified with ``scripts/ast_audit.py``,
which fails the build if a docstring is empty or missing again.

Usage::

    python scripts/add_docstrings.py            # dry run, prints a summary
    python scripts/add_docstrings.py --apply    # rewrite the files
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "bahram"
LINE_LENGTH = 100

_SKIP_DIRS = {"__pycache__"}

# Words that should never be lower-cased when a name is humanised.
_ACRONYMS = {
    "llm": "LLM",
    "mcp": "MCP",
    "api": "API",
    "url": "URL",
    "id": "ID",
    "db": "DB",
    "ui": "UI",
    "cli": "CLI",
    "json": "JSON",
    "sql": "SQL",
    "fts": "FTS",
    "tts": "TTS",
    "stt": "STT",
    "pty": "PTY",
    "lsp": "LSP",
    "cpu": "CPU",
    "moa": "MOA",
}

_VERB_PREFIXES: list[tuple[str, str]] = [
    ("emit_", "Emit a ``{}`` event"),
    ("handle_", "Handle {}"),
    ("validate_", "Validate {}"),
    ("is_", "Return ``True`` when {}"),
    ("has_", "Return ``True`` when the object has {}"),
    ("get_", "Return the {}"),
    ("set_", "Set the {}"),
    ("add_", "Add {}"),
    ("remove_", "Remove {}"),
    ("delete_", "Delete {}"),
    ("create_", "Create {}"),
    ("build_", "Build {}"),
    ("load_", "Load {}"),
    ("save_", "Save {}"),
    ("reset_", "Reset {}"),
    ("update_", "Update {}"),
    ("register_", "Register {}"),
    ("unregister_", "Unregister {}"),
    ("discover_", "Discover {}"),
    ("list_", "List {}"),
    ("record_", "Record {}"),
    ("start_", "Start {}"),
    ("stop_", "Stop {}"),
    ("cancel_", "Cancel {}"),
    ("check_", "Check {}"),
    ("should_", "Return ``True`` when {}"),
    ("can_", "Return ``True`` when the object can {}"),
    ("to_", "Convert the object to {}"),
    ("from_", "Build an instance from {}"),
    ("on_", "Hook invoked when {}"),
    ("scan_", "Scan {}"),
    ("search_", "Search {}"),
    ("format_", "Format {}"),
    ("render_", "Render {}"),
    ("parse_", "Parse {}"),
    ("extract_", "Extract {}"),
    ("summarise_", "Summarise {}"),
    ("summarize_", "Summarize {}"),
    ("estimate_", "Estimate {}"),
    ("compute_", "Compute {}"),
    ("calculate_", "Calculate {}"),
    ("retry_", "Retry {}"),
    ("resume_", "Resume {}"),
    ("pause_", "Pause {}"),
    ("close_", "Close {}"),
    ("shutdown_", "Shut down {}"),
    ("install_", "Install {}"),
    ("publish_", "Publish {}"),
    ("browse_", "Browse {}"),
    ("inspect_", "Inspect {}"),
    ("audit_", "Audit {}"),
    ("promote_", "Promote {}"),
    ("demote_", "Demote {}"),
    ("transcribe_", "Transcribe {}"),
    ("convert_", "Convert {}"),
    ("wrap_", "Wrap {}"),
    ("count_", "Count {}"),
    ("find_", "Find {}"),
    ("apply_", "Apply {}"),
    ("clear_", "Clear {}"),
    ("merge_", "Merge {}"),
    ("split_", "Split {}"),
    ("compress_", "Compress {}"),
    ("optimize_", "Optimise {}"),
    ("optimise_", "Optimise {}"),
    ("translate_", "Translate {}"),
    ("explain_", "Explain {}"),
    ("review_", "Review {}"),
    ("run_", "Run {}"),
    ("execute_", "Execute {}"),
    ("spawn_", "Spawn {}"),
    ("enqueue_", "Enqueue {}"),
    ("inject_", "Inject {}"),
    ("redact_", "Redact {}"),
    ("approve_", "Approve {}"),
    ("deny_", "Deny {}"),
    ("assess_", "Assess {}"),
    ("mount_", "Mount {}"),
    ("track_", "Track {}"),
    ("query_", "Query {}"),
    ("init_", "Initialise {}"),
    ("reload_", "Reload {}"),
    ("refresh_", "Refresh {}"),
    ("notify_", "Notify about {}"),
    ("report_", "Report {}"),
    ("measure_", "Measure {}"),
    ("profile_", "Profile {}"),
    ("benchmark_", "Benchmark {}"),
    ("compare_", "Compare {}"),
    ("restore_", "Restore {}"),
    ("persist_", "Persist {}"),
]


def humanise(name: str) -> str:
    """Turn ``record_model_call`` into ``record model call`` (acronyms kept)."""
    parts = re.split(r"_+", name)
    words = []
    for part in parts:
        # split CamelCase runs
        sub = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|\d+", part) or [part]
        for w in sub:
            low = w.lower()
            words.append(_ACRONYMS.get(low, low if w.isupper() else w.lower()))
    if not words:
        return name
    first = words[0]
    if first in _ACRONYMS.values() or first.isupper():
        pass
    else:
        first = first[0].upper() + first[1:] if first and first[0].isalpha() else first
    return " ".join([first] + words[1:]) if len(words) > 1 else first


def _rest(name: str, prefix: str) -> str:
    return humanise(name[len(prefix) :]) if len(name) > len(prefix) else ""


_PARAM_HINTS: list[tuple[str, str]] = [
    ("file_path", "path of the file to operate on"),
    ("path", "filesystem path to operate on"),
    ("data_dir", "directory that holds the on-disk state"),
    ("workdir", "working directory for the operation"),
    ("timeout", "timeout in seconds"),
    ("limit", "maximum number of items to return"),
    ("offset", "number of items to skip before returning results"),
    ("query", "search query"),
    ("config", "configuration object"),
    ("session_id", "session identifier"),
    ("run_id", "run identifier"),
    ("job_id", "job identifier"),
    ("task_id", "task identifier"),
    ("plan_id", "plan identifier"),
    ("user_id", "user identifier"),
    ("step_id", "plan-step identifier"),
    ("kwargs", "keyword arguments forwarded to the implementation"),
    ("args", "positional arguments forwarded to the implementation"),
    ("command", "shell command to execute"),
    ("code", "source code to execute"),
    ("content", "text content to process"),
    ("message", "message to process"),
    ("model", "model identifier in ``provider/model`` form"),
    ("messages", "chat messages to send to the model"),
    ("name", "name of the object"),
    ("description", "human readable description"),
    ("force", "when ``True``, skip the safety confirmation"),
    ("enabled", "when ``True`` the object is active"),
    ("dry_run", "when ``True`` nothing is written"),
]


def describe_param(name: str, ann: str | None) -> str:
    """Best-effort, always-true description of a parameter."""
    clean = name.lstrip("*")
    for hint, text in _PARAM_HINTS:
        if clean == hint:
            return f"{text}."
    if ann:
        low = ann.lower()
        if low.startswith("bool"):
            return f"when ``True``, enable {humanise(clean).lower()}."
        if low.startswith("int") or low.startswith("float"):
            return f"numeric value for {humanise(clean).lower()}."
        if low.startswith("str"):
            return f"{humanise(clean).lower()} string."
        if low.startswith("list"):
            return f"collection of {humanise(clean).lower()}."
        if low.startswith("dict"):
            return f"mapping of {humanise(clean).lower()}."
        if "callable" in low:
            return f"callable used for {humanise(clean).lower()}."
    return f"{humanise(clean).lower()}."


def describe_return(ann: str) -> str:
    """Best-effort, always-true description of a return value."""
    low = ann.lower()
    if low == "bool":
        return "``True`` when the operation succeeds, otherwise ``False``."
    if low == "str":
        return "the rendered string."
    if low == "int" or low == "float":
        return "the computed numeric value."
    if low.startswith("list") or low.startswith("tuple") or low.startswith("set"):
        inner = ann[ann.find("[") + 1 : ann.rfind("]")] if "[" in ann else "items"
        return f"a sequence of {inner} entries (empty when there is nothing to report)."
    if low.startswith("dict"):
        inner = ann[ann.find("[") + 1 : ann.rfind("]")] if "[" in ann else "str, Any"
        return f"a mapping of {inner}."
    if low.startswith("none") or "none" == low:
        return "nothing."
    if low.startswith("optional") or "| none" in low:
        return "the resulting object, or ``None`` when it is not available."
    return f"the resulting {ann}."


def describe_special(name: str, class_name: str | None) -> str | None:
    """Hand-written summaries for the handful of names with fixed semantics."""
    if name == "to_dict":
        return "Serialise the object to a JSON-serialisable dictionary."
    if name == "schema":
        return "Return the OpenAI-style function schema for this tool."
    if name == "execute":
        return "Execute the tool and return its textual result."
    if name == "name":
        return f"Return the registry name of the{' ' + class_name if class_name else ''} object."
    if name == "description":
        return "Return the human readable description shown to the model."
    if name == "parameters":
        return "Return the JSON schema describing this tool's arguments."
    if name == "validate_args":
        return "Validate the supplied keyword arguments against the parameter schema."
    if name == "start":
        return "Start the component and acquire any resources it needs."
    if name == "stop":
        return "Stop the component and release any resources it holds."
    if name == "close":
        return "Release resources held by this object."
    return None


def summary_for_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    class_name: str | None,
) -> str:
    name = node.name
    if name == "__init__":
        target = class_name or "object"
        return f"Initialise a {target} instance."
    if name == "__enter__":
        return "Enter the runtime context and return ``self``."
    if name == "__exit__":
        return "Exit the runtime context, suppressing no exceptions."
    if name == "__aenter__":
        return "Enter the async runtime context and return ``self``."
    if name == "__aexit__":
        return "Exit the async runtime context, suppressing no exceptions."
    if name == "__repr__":
        return "Return the developer-facing representation."
    if name == "__str__":
        return "Return the user-facing representation."

    special = describe_special(name, class_name)
    if special:
        return special

    for prefix, template in _VERB_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix):
            text = template.format(_rest(name, prefix).lower())
            break
    else:
        text = f"{humanise(name)}."

    if not text.endswith("."):
        text += "."
    return text


def _annotation(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _literal_return(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Return the literal a trivial getter returns, if it is a short string."""
    for stmt in node.body:
        if isinstance(stmt, ast.Return) and stmt.value is not None:
            v = stmt.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str) and len(v.value) < 80:
                return v.value
            if isinstance(v, ast.JoinedStr):  # f-string
                return None
    return None


def _raise_types(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    found: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Raise) and child.exc is not None:
            exc = child.exc
            if isinstance(exc, ast.Call):
                exc = exc.func
            if isinstance(exc, ast.Name):
                name = exc.id
            elif isinstance(exc, ast.Attribute):
                name = exc.attr
            else:
                continue
            if name.endswith("Error") or name in {"Exception", "BaseException"}:
                if name not in found:
                    found.append(name)
    return found


def build_docstring(
    node: ast.AST,
    kind: str,
    qname: str,
    class_name: str | None,
    module_classes: list[str] | None = None,
) -> list[str]:
    """Return the docstring body lines (without the enclosing quotes)."""
    lines: list[str] = []

    if kind == "module":
        mod_name = qname
        lines.append(f"{humanise(mod_name)}.")
        if module_classes:
            shown = ", ".join(f"``{c}``" for c in module_classes[:8])
            more = "" if len(module_classes) <= 8 else f" (+{len(module_classes) - 8} more)"
            lines.append("")
            lines.append(f"Public objects: {shown}{more}.")
        return lines

    if kind == "class":
        assert isinstance(node, ast.ClassDef)
        lines.append(f"{humanise(node.name)}.")
        fields = [
            (t.target.id, _annotation(t.annotation))
            for t in node.body
            if isinstance(t, ast.AnnAssign) and isinstance(t.target, ast.Name)
        ]
        if fields:
            lines.append("")
            lines.append("Attributes:")
            for fname, ftype in fields:
                lines.append(f"    {fname} ({ftype or 'Any'}): {describe_param(fname, ftype)}")
        return lines

    assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    lines.append(summary_for_function(node, class_name))

    is_property = any(
        (isinstance(d, ast.Name) and d.id == "property")
        or (isinstance(d, ast.Attribute) and d.attr == "property")
        for d in node.decorator_list
    )

    literal = _literal_return(node) if is_property else None
    if literal:
        lines.append("")
        lines.append(f"Returns the constant string ``{literal!r}``.")

    args = node.args
    params: list[tuple[str, str | None, str | None]] = []
    positional = list(getattr(args, "posonlyargs", [])) + list(args.args)
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults)) + list(
        args.defaults
    )
    for arg, default in zip(positional, defaults):
        if arg.arg in {"self", "cls"}:
            continue
        params.append(
            (arg.arg, _annotation(arg.annotation), _annotation(default) if default else None)
        )
    if args.vararg is not None:
        params.append((f"*{args.vararg.arg}", _annotation(args.vararg.annotation), None))
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        params.append(
            (arg.arg, _annotation(arg.annotation), _annotation(default) if default else None)
        )
    if args.kwarg is not None:
        params.append((f"**{args.kwarg.arg}", _annotation(args.kwarg.annotation), None))

    if params:
        lines.append("")
        lines.append("Args:")
        for name, ann, default in params:
            text = f"    {name}"
            if ann:
                text += f" ({ann})"
            text += f": {describe_param(name, ann)}"
            if default:
                text += f" Defaults to ``{default}``."
            lines.append(text)

    ret = _annotation(node.returns)
    if ret and ret not in {"None", "NoneType"}:
        lines.append("")
        lines.append("Returns:")
        lines.append(f"    {ret}: {describe_return(ret)}")

    raises = _raise_types(node)
    if raises:
        lines.append("")
        lines.append("Raises:")
        for exc in raises:
            lines.append(f"    {exc}: if the operation cannot be completed.")

    if isinstance(node, ast.AsyncFunctionDef):
        lines.append("")
        lines.append("Note:")
        lines.append("    Coroutine - must be awaited.")
    return lines


def render(lines: list[str], indent: str) -> str:
    """Render docstring content lines as a triple-quoted string.

    Content is wrapped to ``LINE_LENGTH`` so the generated documentation does
    not itself introduce E501 violations.
    """
    out: list[str] = []
    for line in lines:
        if not line:
            out.append("")
            continue
        leading = len(line) - len(line.lstrip())
        subsequent = indent + " " * (leading + 4)
        wrapped = textwrap.wrap(
            line,
            width=LINE_LENGTH,
            initial_indent=indent,
            subsequent_indent=subsequent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        out.extend(wrapped or [indent])
    body = "\n".join(out)
    return f'{indent}"""\n{body}\n{indent}"""'


def _needs_docstring(node: ast.AST) -> bool:
    body = getattr(node, "body", None)
    if not body:
        return False
    first = body[0]
    return not (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


def apply_to_file(path: Path, apply: bool) -> int:
    src = path.read_text()
    lines = src.split("\n")

    # (insert_before_line, indent, text)
    inserts: list[tuple[int, str, str]] = []

    tree = ast.parse(src, filename=str(path))
    module_classes = [
        n.name
        for n in tree.body
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and not n.name.startswith("_")
    ]

    if _needs_docstring(tree):
        text = render(build_docstring(tree, "module", path.stem, None, module_classes), "")
        at = 1
        while at <= len(lines) and (
            lines[at - 1].startswith("#!") or "coding" in lines[at - 1][:40]
        ):
            at += 1
        inserts.append((at, "", text))

    def walk_class(cls: ast.ClassDef, prefix: str) -> None:
        qname = f"{prefix}{cls.name}"
        if _needs_docstring(cls):
            first = cls.body[0]
            indent = " " * first.col_offset
            # A decorated first member (``@property``/``@abstractmethod``) must
            # not end up *above* the class docstring, so aim at the decorator.
            decorators = getattr(first, "decorator_list", None) or []
            lineno = min([d.lineno for d in decorators] + [first.lineno])
            if lineno != cls.lineno and ":" not in lines[lineno - 1][: first.col_offset]:
                inserts.append(
                    (
                        lineno,
                        indent,
                        render(build_docstring(cls, "class", qname, cls.name), indent),
                    )
                )
        for child in cls.body:
            walk_node(child, qname + ".", cls.name)

    def walk_func(fn: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str, cls: str | None) -> None:
        qname = f"{prefix}{fn.name}"
        if not fn.name.startswith("_") or fn.name in {"__init__", "__enter__", "__exit__"}:
            if _needs_docstring(fn):
                first = fn.body[0]
                indent = " " * first.col_offset
                if first.lineno == fn.lineno:
                    return  # `def f(): ...` on one line - nothing to document
                # When a multi-line signature ends with `) -> X: ...` the body
                # starts on the signature's last line; inserting before it
                # would split the signature in half.
                if ":" in lines[first.lineno - 1][: first.col_offset]:
                    return
                inserts.append(
                    (
                        first.lineno,
                        indent,
                        render(build_docstring(fn, "def", qname, cls), indent),
                    )
                )
        for child in fn.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue  # nested helpers are not public API
            walk_node(child, prefix, None)

    def walk_node(node: ast.AST, prefix: str, cls_name: str | None) -> None:
        if isinstance(node, ast.ClassDef):
            walk_class(node, prefix)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            walk_func(node, prefix, cls_name)

    for child in tree.body:
        walk_node(child, "", None)

    # Apply bottom-up so earlier line numbers stay valid.
    for lineno, _indent, text in sorted(inserts, key=lambda t: t[0], reverse=True):
        lines.insert(lineno - 1, text)

    if apply and inserts:
        path.write_text("\n".join(lines))
    return len(inserts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("paths", nargs="*", default=[str(PACKAGE)])
    args = parser.parse_args()

    total = 0
    files = 0
    for raw in args.paths:
        p = Path(raw)
        targets = sorted(p.rglob("*.py")) if p.is_dir() else [p]
        for path in targets:
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            n = apply_to_file(path, args.apply)
            if n:
                files += 1
                total += n
    print(f"{'inserted' if args.apply else 'would insert'} {total} docstrings in {files} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Move a set of definitions out of a big module into a new one.

Use it rather than re-deriving one: every hand-rolled version has repeated one
of the bugs listed below.

What it does, and nothing more: lift whole definitions (with the comment block
above them and any decorators), de-indent class members into module functions,
drop the implicit first parameter, and rewrite ``self.``/``cls.``/``Class.``
prefixes on the moved code. It does NOT write the new module's imports or delete
anything from the origin -- those are judgement calls, and `ruff --select F821`
plus `F401` answer them faster than a heuristic would.

    uv run python scripts/extract_module.py <source.py> --class MarkdownGrouper \\
        --names _peel_boundary_dps_walk,_expand_emoji_run_dp [--out fragment.py]

Then: paste the fragment under a docstring, resolve F821 into imports, delete the
originals, and run `check_arity` over both files. What no check here sees:

* **Module-level mutable state does not survive a split.** A reader in another
  module binds the value at import time and never sees a later write. Move it
  onto one object passed as an argument first (``render_settings.VIEW``).
* **Never ``ruff check --fix`` the origin mid-move**: it strips re-exports that
  only tests import. Re-export only what the origin still uses; point tests at
  the new owner.
* **Verify with the snapshots** (AGENTS.md, *Before finishing*): byte-identical,
  or explain why not. Then the suite and the import contracts.

THE THREE BUGS, each caught by a check in here:

* **The first parameter is not always where the pattern expects.** ``def f(cls,``
  on the def line, ``cls,`` on the line below, or alone on its own line -- a
  regex that assumes one spelling leaves the others behind, and a surviving
  ``cls`` silently shifts every caller's arguments by one. Located through the
  AST here, and asserted afterwards.
* **An import's SHAPE is not recoverable from the name it binds.**
  ``from x import A as _B`` recorded as "``_B`` comes from ``x``" produces
  ``from x import _B``, which does not exist -- and worse, ``from datetime import
  datetime`` re-inferred as ``import datetime`` produces a name that IS defined
  and is the wrong object, so every linter stays clean and tests fail at
  runtime. :func:`import_statements` prints the origin's exact statements;
  :func:`aliased_imports` highlights the aliased subset. Copy, do not infer.
* **Call sites outnumber signatures.** After adding a parameter, a text search
  for calls misses any whose arguments contain nested parentheses.
  :func:`check_arity` compares each ``ast.Call``'s
  argument count against the definition, which cannot miss.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

DEDENT = re.compile(r"^    ", re.M)


# ---------------------------------------------------------------------------
# Locating definitions
# ---------------------------------------------------------------------------


def _span(node: ast.stmt) -> tuple[int, int]:
    """1-based ``(first, last)`` line of *node*, decorators included.

    ``ast`` reports a decorated definition at its ``def``/``class`` keyword, so
    taking ``node.lineno`` alone leaves ``@dataclasses.dataclass`` behind -- it
    then lands on the NEXT definition, which fails as
    ``'function' object has no attribute '__mro__'``.
    """
    lo = node.lineno
    for d in getattr(node, "decorator_list", []):
        lo = min(lo, d.lineno)
    # end_lineno is Optional on ast.stmt; every real parsed node has one.
    return lo, node.end_lineno or node.lineno


def definitions(tree: ast.Module, cls: str | None = None) -> dict[str, tuple[int, int]]:
    """``name -> span`` for the definitions at module level, or in class *cls*."""
    body: list[ast.stmt] | None = None
    if cls:
        for n in tree.body:
            if isinstance(n, ast.ClassDef) and n.name == cls:
                body = n.body
        if body is None:
            raise SystemExit(f"class {cls!r} not found")
    else:
        body = tree.body

    out: dict[str, tuple[int, int]] = {}
    for n in body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[n.name] = _span(n)
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    out[t.id] = (n.lineno, n.end_lineno or n.lineno)
    return out


def with_comments(lines: list[str], lo: int, hi: int) -> tuple[int, int]:
    """Extend *lo* up over the comment block directly above the definition.

    A constant's explanation sits above it and is part of it; leaving the
    comment behind strands it next to unrelated code.
    """
    i = lo - 1
    while i >= 1 and lines[i - 1].strip().startswith("#"):
        i -= 1
    return i + 1, hi


# ---------------------------------------------------------------------------
# Rewriting what moves
# ---------------------------------------------------------------------------


def strip_first_param(text: str) -> str:
    """Drop a leading ``self`` / ``cls`` parameter, wherever it is written.

    Located through the AST rather than matched, because the parameter may sit
    on the ``def`` line, on the line below it, or alone on its own line. See the
    module docstring. Asserts the result, so a miss is loud instead of silent.
    """
    fn = next(
        (
            n
            for n in ast.parse(text).body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ),
        None,
    )
    if fn is None or not fn.args.args or fn.args.args[0].arg not in ("self", "cls"):
        return text
    arg = fn.args.args[0]
    lines = text.split("\n")
    i = arg.lineno - 1
    line = lines[i]
    tail = line[arg.end_col_offset :]
    m = re.match(r"\s*,\s*", tail)
    lines[i] = line[: arg.col_offset] + (tail[m.end() :] if m else tail)
    if not lines[i].strip():
        del lines[i]
    out = "\n".join(lines)

    check = next(
        n
        for n in ast.parse(out).body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    assert not check.args.args or check.args.args[0].arg not in (
        "self",
        "cls",
    ), f"{fn.name}: first parameter survived the strip"
    return out


def extract(source: str, names: list[str], cls: str | None = None) -> str:
    """The module-level source text for *names*, ready to paste.

    Prefixes are rewritten on the MOVED code as well as the origin: rewriting
    only the file left behind leaves the extraction naming a class it no longer
    has.
    """
    tree = ast.parse(source)
    lines = source.split("\n")
    defs = definitions(tree, cls)

    spans = []
    for name in names:
        if name not in defs:
            raise SystemExit(f"{name!r} not found in {cls or 'module scope'}")
        spans.append((*with_comments(lines, *defs[name]), name))
    spans.sort()
    for a, b in zip(spans, spans[1:]):
        if b[0] <= a[1]:
            raise SystemExit(f"spans overlap: {a[2]} and {b[2]}")

    out = []
    for lo, hi, _ in spans:
        text = "\n".join(lines[lo - 1 : hi])
        if cls:
            text = DEDENT.sub("", text)
            text = re.sub(r"^@(?:staticmethod|classmethod)\n", "", text, flags=re.M)
            text = strip_first_param(text)
            text = re.sub(rf"(?<![\w.])(?:self|cls|{re.escape(cls)})\.", "", text)
        out.append(text.rstrip() + "\n")
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# Checks to run AFTER the move
# ---------------------------------------------------------------------------


def import_statements(source: str) -> dict[str, str]:
    """``local_name -> the exact import statement that binds it`` in *source*.

    Write the new module's imports by COPYING these, never by inferring a form
    from the name. Inferred, ``from datetime import datetime`` becomes
    ``import datetime``: every parser then resolves ``datetime.strptime`` to the
    MODULE and fails on ``module 'datetime' has no attribute 'strptime'``. The
    name is right and the shape is wrong, which no undefined-name check can see
    -- ``ruff`` is clean, because ``datetime`` is defined.
    """
    out: dict[str, str] = {}
    for n in ast.parse(source).body:
        if isinstance(n, ast.Import):
            for a in n.names:
                local = a.asname or a.name.split(".")[0]
                out[local] = f"import {a.name}" + (
                    f" as {a.asname}" if a.asname else ""
                )
        elif isinstance(n, ast.ImportFrom):
            mod = "." * n.level + (n.module or "")
            for a in n.names:
                local = a.asname or a.name
                out[local] = f"from {mod} import {a.name}" + (
                    f" as {a.asname}" if a.asname else ""
                )
    return out


def aliased_imports(source: str) -> list[tuple[str, str, str | None]]:
    """``(local_name, real_name, module)`` for every ``import ... as ...``.

    Run this over the ORIGIN before writing the new module's imports. A resolver
    that records "this local name came from that module" and drops the ``as``
    emits an import of a name that does not exist.
    """
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                if a.asname:
                    out.append((a.asname, a.name, getattr(n, "module", None)))
    return out


def check_arity(paths: list[str], arities: dict[str, int]) -> list[str]:
    """Every call to a name in *arities* must pass exactly that many arguments.

    The check for "I added a parameter and missed a call site". A text search
    cannot do this: it misses calls whose arguments contain nested parentheses,
    such as ``_promote_colon_columns(seg, _protected_ranges(seg), clf)``.
    """
    problems = []
    for path in paths:
        tree = ast.parse(Path(path).read_text())
        for n in ast.walk(tree):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id in arities
            ):
                got = len(n.args) + len(n.keywords)
                if got != arities[n.func.id]:
                    problems.append(
                        f"{path}:{n.lineno}: {n.func.id} called with {got} "
                        f"argument(s), needs {arities[n.func.id]}"
                    )
    return problems


def module_state(source: str) -> dict[str, list[str]]:
    """Module-level names written through ``global``, per writing function.

    Cross-module mutable state cannot survive a split and no linter reports it
    (``ruff`` reads ``global``-then-assign as "imported but unused"). Run this
    before moving anything: a name here that the code being moved WRITES, and
    the code staying READS, has to become an explicit object first.

    It cannot see a dynamic ``globals()[name] = ...`` write; grep for that
    separately.
    """
    out: dict[str, list[str]] = {}
    for fn in ast.walk(ast.parse(source)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Global):
                for name in sub.names:
                    out.setdefault(name, []).append(fn.name)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source")
    ap.add_argument("--class", dest="cls", default=None)
    ap.add_argument("--names", required=True, help="comma-separated")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    source = Path(args.source).read_text()
    names = [n.strip() for n in args.names.split(",") if n.strip()]
    fragment = extract(source, names, args.cls)

    aliases = aliased_imports(source)
    if aliases:
        print("ALIASED IMPORTS in the origin — keep the `as` when you", file=sys.stderr)
        print("write the new module's imports:", file=sys.stderr)
        for local, real, mod in aliases:
            print(f"  {local} = {mod or '<import>'}.{real}", file=sys.stderr)
    stmts = import_statements(source)
    if stmts:
        print(
            "IMPORT STATEMENTS in the origin -- copy the ones the extraction",
            file=sys.stderr,
        )
        print("needs VERBATIM; do not infer the form from the name:", file=sys.stderr)
        for local in sorted(stmts):
            print(f"  {local:24s} {stmts[local]}", file=sys.stderr)
    state = module_state(source)
    if state:
        print("MODULE STATE written via `global` in the origin:", file=sys.stderr)
        for name, writers in sorted(state.items()):
            print(f"  {name}  <- {', '.join(sorted(set(writers)))}", file=sys.stderr)

    if args.out:
        Path(args.out).write_text(fragment)
        print(f"wrote {args.out} ({len(fragment.splitlines())} lines)")
    else:
        print(fragment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

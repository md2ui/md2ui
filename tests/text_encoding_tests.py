"""Every text file md2ui reads or writes names its encoding.

md2ui's documents, MEANINGS.md, skills and patterns are UTF-8 and full of emoji,
`°` and `→`. Python before 3.15 opens a file that names no encoding in the
locale's encoding, which on Windows is the ANSI code page: there an unnamed read
turns `Café ☕` into mojibake or stops on a byte the code page lacks. So every
`read_text`, `write_text` and text-mode builtin `open` under `src/md2ui` names
`encoding=`. The walk is syntactic: `webbrowser.open` and other `.open` methods
are not files and are not looked at.

Run with: uv run python scripts/run_tests.py
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "md2ui"


def _open_mode(call: ast.Call) -> object:
    """The mode a builtin `open` call names, or None when it names none."""
    for keyword in call.keywords:
        if keyword.arg == "mode":
            return (
                keyword.value.value if isinstance(keyword.value, ast.Constant) else ...
            )
    if len(call.args) > 1:
        mode = call.args[1]
        return mode.value if isinstance(mode, ast.Constant) else ...
    return None


def _unnamed_encodings(source: str) -> list[int]:
    """The lines of *source* holding a text read or write that names no encoding."""
    lines = []
    for call in ast.walk(ast.parse(source)):
        if not isinstance(call, ast.Call):
            continue
        if any(keyword.arg == "encoding" for keyword in call.keywords):
            continue
        func = call.func
        if isinstance(func, ast.Attribute) and func.attr in ("read_text", "write_text"):
            lines.append(call.lineno)
        elif isinstance(func, ast.Name) and func.id == "open":
            mode = _open_mode(call)
            if not (isinstance(mode, str) and "b" in mode):
                lines.append(call.lineno)
    return sorted(lines)


def test_the_walk_sees_each_unnamed_spelling():
    """A guard that never fires is indistinguishable from one that passes."""
    source = (
        "p.read_text()\n"
        "p.write_text(s)\n"
        "open(f)\n"
        "open(f, 'w')\n"
        "open(f, mode=m)\n"
        "p.read_text(encoding='utf-8')\n"
        "open(f, 'rb')\n"
        "open(f, mode='wb')\n"
        "webbrowser.open(href)\n"
    )
    assert _unnamed_encodings(source) == [1, 2, 3, 4, 5]


def test_every_text_read_and_write_in_src_names_its_encoding():
    found = [
        f"{path.relative_to(SRC.parent)}:{line}"
        for path in sorted(SRC.rglob("*.py"))
        for line in _unnamed_encodings(path.read_text(encoding="utf-8"))
    ]
    assert not found, f"{len(found)} text reads/writes name no encoding:\n" + "\n".join(
        found
    )


TESTS = [
    test_the_walk_sees_each_unnamed_spelling,
    test_every_text_read_and_write_in_src_names_its_encoding,
]


if __name__ == "__main__":
    for t in TESTS:
        t()
        print(f"  ✓ {t.__name__}")
    print(f"All {len(TESTS)} tests passed.")

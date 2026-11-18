"""The LLM's CLI: one command, four verbs, each of which runs once and exits.

    md2ui group  doc.md               -> grouping-ast.json beside the document
    md2ui layout doc.md --width N     -> layout-dump-<N>.json beside the document
    md2ui render doc.md --width N     -> render-<N>w.png beside the document
    md2ui check  doc.md               -> the MCP ``check`` tool's issues, printed
    md2ui check  --theme THEME.md     -> the theme linted against its contract

Built for an agent, not for a person at a window. Every verb takes the Markdown
itself and runs the pipeline from the start, so there is no intermediate file to
keep in step and no "rebuild the AST first" to forget. None of them watches a
file, opens a window or reads stdin: a command that waits for input hangs the
agent that ran it. The output is the path of each file written, plus the
diagnostics that change what the author should do next (``[theme]``, ``[url]``).
Exit status: 0 written, 1 nothing written (the grouper produced no tree, the
page is too big for one bitmap, or the PNG did not encode), 2 bad arguments.
``check`` exits 1 when the document has an error-level issue; the theme lint
reports and never fails (ADR-501). An empty document is not an error: it groups
to an empty root and renders a blank page, as in both snapshots.

The user's window, with its live reload, is ``md2ui.app`` (``md2ui-app``). This
module never imports it — see the contracts in ``pyproject.toml``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from md2ui import session, theme_lint
from md2ui.check import check_markdown
from md2ui.pipeline.layout_generator import LayoutGenerator
from md2ui.pipeline.layout_render import load_background_images
from md2ui.pipeline.render_settings import VIEW
from md2ui.utils.image_cache import ImageCache


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md2ui",
        description="Run the md2ui pipeline once on a Markdown document.",
    )
    verbs = parser.add_subparsers(dest="verb", required=True)

    group = verbs.add_parser("group", help="Write the grouping AST as JSON")
    group.add_argument("markdown", help="Path to the Markdown document")
    group.add_argument(
        "--out", help="Output path (default: grouping-ast.json beside it)"
    )

    layout = verbs.add_parser("layout", help="Write the generated layout AST as JSON")
    render = verbs.add_parser("render", help="Render the document to a PNG")
    for sub, default_out in (
        (layout, "layout-dump-<width>.json"),
        (render, "render-<width>w.png"),
    ):
        sub.add_argument("markdown", help="Path to the Markdown document")
        sub.add_argument(
            "--out", help=f"Output path (default: {default_out} beside it)"
        )
        sub.add_argument(
            "--width",
            type=int,
            default=1024,
            help="Layout width in px; a document that needs more gets its minimum",
        )
        sub.add_argument(
            "--theme", help="Path to THEME.md (default: beside the document, else cwd)"
        )
        sub.add_argument(
            "--bento",
            action="store_true",
            help="Force the bento mosaic layout on, regardless of the theme's `Layout:`",
        )

    check = verbs.add_parser(
        "check", help="Print a document's authoring issues, or lint a theme"
    )
    check.add_argument(
        "markdown", nargs="?", help="Path to the Markdown document (omit to lint)"
    )
    check.add_argument(
        "--theme", help="Path to THEME.md (default: beside the document, else cwd)"
    )

    render.add_argument(
        "--scale", type=float, default=1.0, help="Pixel scale (e.g. 2 for retina)"
    )
    render.add_argument(
        "--wireframe", action="store_true", help="Draw the layout-AST wireframe"
    )
    render.add_argument("--debug", action="store_true", help="Draw the spacing gaps")
    render.add_argument(
        "--debug-padding", action="store_true", help="Draw the padding rings"
    )
    render.add_argument(
        "--text-boxes", action="store_true", help="Draw each text's real box"
    )
    return parser


def _group(md: Path, args: argparse.Namespace) -> int:
    ast = session.group_markdown(
        md.read_text(encoding="utf-8"), session.load_grouping_kit()
    )
    if ast is None:
        print(f"[group] {md}: nothing to group", file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else md.parent / "grouping-ast.json"
    out.write_text(json.dumps(ast.to_dict(), indent=4), encoding="utf-8")
    print(f"[group] saved {out}")
    return 0


def _layout_or_render(md: Path, args: argparse.Namespace) -> int:
    theme_path = session.resolve_theme_path(md, args.theme)
    theme = session.load_theme(theme_path)
    if theme_path:
        print(f"[theme] {theme_path}")
    fonts = session.load_fonts(theme)
    ast = session.group_markdown(
        md.read_text(encoding="utf-8"), session.load_grouping_kit()
    )
    if ast is None:
        print(f"[{args.verb}] {md}: nothing to group", file=sys.stderr)
        return 1
    root, node_index = session.prepare(ast, theme)
    gen = LayoutGenerator()
    if args.bento:
        gen.bento_override = True

    if args.verb == "layout":
        scene = session.build_scene(gen, root, node_index, theme, fonts, args.width)
        session.report_url_params(gen)
        out = args.out or str(md.parent / f"layout-dump-{int(scene.width)}.json")
        Path(out).write_text(
            json.dumps(scene.layout.to_dict(), indent=4), encoding="utf-8"
        )
        print(f"[layout] saved {out}")
        return 0

    VIEW.wireframe = args.wireframe
    VIEW.debug_spacing = args.debug
    VIEW.debug_padding = args.debug_padding
    VIEW.text_boxes = args.text_boxes
    session.load_placeholders()
    image_cache = ImageCache()
    session.wait_for_images(image_cache, node_index)
    scene = session.build_scene(gen, root, node_index, theme, fonts, args.width)
    session.report_url_params(gen)
    out = args.out or str(md.parent / f"render-{int(scene.width)}w.png")
    try:
        ok = session.render_png(
            scene,
            node_index,
            theme,
            fonts,
            image_cache,
            load_background_images(theme),
            args.scale,
            out,
        )
    except session.PageTooLarge as refused:
        print(f"[render] {md}: {refused}", file=sys.stderr)
        return 1
    return 0 if ok else 1


def _check(md: Path | None, args: argparse.Namespace) -> int:
    """The document's issues, as the MCP ``check`` tool returns them for the same
    theme (this verb finds the theme beside the document, the server uses its
    ``--theme``); with no document, the theme's lint against its contract."""
    if md is None:
        messages = theme_lint.lint(Path(args.theme)).messages
        for message in messages:
            print(f"[theme] {message}")
        if not messages:
            print("[theme] the theme draws its contract as declared")
        return 0
    contract = theme_lint.answer_contract(session.resolve_theme_path(md, args.theme))
    issues = check_markdown(
        md.read_text(encoding="utf-8"), session.load_grouping_kit(), contract
    )
    for issue in issues:
        print(f"{issue['level']} {issue['code']}: {issue['message']}")
        if "line" in issue:
            at = f"  line {issue['line']}: "
            print(f"{at}{issue['text']}")
            for replacement in issue["replacements"]:
                print(f"{'  ->'.ljust(len(at))}{replacement}")
    if not issues:
        print(f"[check] {md}: no issues")
    return 1 if any(issue["level"] == "error" for issue in issues) else 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.verb == "check" and args.markdown is None:
        if not args.theme or not Path(args.theme).is_file():
            parser.error("check needs a document, or --theme with a THEME.md")
        return _check(None, args)
    md = Path(args.markdown)
    if not md.is_file():
        parser.error(f"no such file: {md}")
    if args.verb == "group":
        return _group(md, args)
    if args.verb == "check":
        return _check(md, args)
    return _layout_or_render(md, args)


if __name__ == "__main__":
    raise SystemExit(main())

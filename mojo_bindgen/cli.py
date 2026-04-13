"""Command-line interface for mojo-bindgen."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mojo_bindgen.codegen.mojo_emit import MojoEmitOptions, emit_unit
from mojo_bindgen.parsing.parser import ClangParser, ParseError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mojo-bindgen",
        description="Generate Mojo FFI from a C header using libclang.",
    )
    p.add_argument(
        "header",
        type=Path,
        help="Path to the primary C header file",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write output to this file (default: stdout)",
    )
    p.add_argument(
        "--library",
        default=None,
        metavar="NAME",
        help="Logical library name in the IR (default: stem of the header path)",
    )
    p.add_argument(
        "--link-name",
        default=None,
        metavar="NAME",
        help="Shared-library link name (default: same as --library)",
    )
    p.add_argument(
        "--compile-arg",
        action="append",
        default=None,
        metavar="FLAG",
        help="Extra clang flag (repeatable). If omitted, use built-in system include probing.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit IR as JSON instead of Mojo source",
    )
    p.add_argument(
        "--linking",
        choices=("external_call", "owned_dl_handle"),
        default="external_call",
        help="FFI linking mode for Mojo output (ignored with --json)",
    )
    p.add_argument(
        "--library-path-hint",
        default=None,
        metavar="PATH",
        help="Path hint for OwnedDLHandle when --linking owned_dl_handle",
    )
    p.add_argument(
        "--emit-align",
        dest="emit_align",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Emit @align(N) on structs from C alignment (Mojo-valid values only); default on (use --no-emit-align to disable)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    header = args.header
    stem = header.stem if header.suffix else str(header)
    library = args.library if args.library is not None else stem
    link_name = args.link_name if args.link_name is not None else library
    compile_args = args.compile_arg

    try:
        parser = ClangParser(
            header,
            library=library,
            link_name=link_name,
            compile_args=compile_args,
            raise_on_error=True,
        )
        unit = parser.run()
    except (ParseError, FileNotFoundError, OSError) as e:
        print(f"mojo-bindgen: {e}", file=sys.stderr)
        return 1

    if args.json:
        text = unit.to_json()
    else:
        opts = MojoEmitOptions(
            linking=args.linking,
            library_path_hint=args.library_path_hint,
            emit_align=args.emit_align,
        )
        text = emit_unit(unit, opts)

    if args.output is None:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

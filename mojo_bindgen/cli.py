"""Command-line interface for mojo-bindgen."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from mojo_bindgen.orchestrator import BindgenOptions, BindgenOrchestrator
from mojo_bindgen.parsing.parser import ParseError

stderr_console = Console(stderr=True)


def run(
    header: Annotated[Path, typer.Argument(help="Path to the primary C header file")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write output to this file (default: stdout).",
            show_default=False,
        ),
    ] = None,
    library: Annotated[
        str | None,
        typer.Option(
            "--library",
            metavar="NAME",
            help="Logical library name in the IR (default: stem of the header path).",
        ),
    ] = None,
    link_name: Annotated[
        str | None,
        typer.Option(
            "--link-name",
            metavar="NAME",
            help="Shared-library link name (default: same as --library).",
        ),
    ] = None,
    compile_arg: Annotated[
        list[str] | None,
        typer.Option(
            "--compile-arg",
            metavar="FLAG",
            help="Extra clang flag (repeatable). If omitted, use built-in system include probing.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit IR as JSON instead of Mojo source.",
        ),
    ] = False,
    linking: Annotated[
        Literal["external_call", "owned_dl_handle"],
        typer.Option(
            "--linking",
            help="FFI linking mode for Mojo output (ignored with --json).",
            case_sensitive=False,
        ),
    ] = "external_call",
    library_path_hint: Annotated[
        str | None,
        typer.Option(
            "--library-path-hint",
            metavar="PATH",
            help="Path hint for OwnedDLHandle when --linking owned_dl_handle.",
        ),
    ] = None,
    strict_abi: Annotated[
        bool,
        typer.Option(
            "--strict-abi",
            help="Preserve parsed C alignment emission behavior. By default, omit @align for ordinary records and keep ABI comments only.",
        ),
    ] = False,
    layout_tests: Annotated[
        bool | None,
        typer.Option(
            "--layout-tests/--no-layout-tests",
            help="Write a Mojo record-layout test sidecar with file output.",
        ),
    ] = None,
    layout_test_output: Annotated[
        Path | None,
        typer.Option(
            "--layout-test-output",
            metavar="PATH",
            help="Write layout-test sidecar to this path.",
            show_default=False,
        ),
    ] = None,
) -> int:
    """Generate Mojo FFI from a C header using libclang.

    Examples:
      mojo-bindgen path/to/header.h -o bindings.mojo
      mojo-bindgen path/to/header.h --json -o unit.json
      mojo-bindgen include/me.h --compile-arg=-I./include -o out.mojo
    """
    try:
        orchestrator = BindgenOrchestrator(
            BindgenOptions(
                header=header,
                library=library,
                link_name=link_name,
                compile_args=compile_arg,
                linking=linking,
                library_path_hint=library_path_hint,
                strict_abi=strict_abi,
                module_comment=True,
                layout_tests=layout_tests,
                json_output=json_output,
                output=output,
                layout_test_output=layout_test_output,
            )
        )
        result = orchestrator.run()
    except (ParseError, FileNotFoundError, OSError) as e:
        stderr_console.print(f"[bold red]mojo-bindgen error:[/bold red] {e}")
        raise typer.Exit(code=1) from e

    if json_output:
        text = result.unit.to_json()
    else:
        text = result.bindings_source

    if output is None:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        output.write_text(text, encoding="utf-8")
    if result.layout_test_source is not None:
        sidecar = layout_test_output
        if sidecar is None and output is not None:
            sidecar = output.with_name(f"{output.stem}_layout_tests.mojo")
        if sidecar is not None:
            sidecar.write_text(result.layout_test_source, encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    cli_args = argv if argv is not None else sys.argv[1:]
    previous_argv = sys.argv[:]
    sys.argv = ["mojo-bindgen", *cli_args]
    try:
        typer.run(run)
        return 0
    except typer.Exit as e:
        return e.exit_code
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else 0
    finally:
        sys.argv = previous_argv


if __name__ == "__main__":
    raise SystemExit(main())

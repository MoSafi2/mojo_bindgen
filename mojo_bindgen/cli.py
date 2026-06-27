"""Command-line interface for mojo-bindgen."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from mojo_bindgen import __version__
from mojo_bindgen.orchestrator import BindgenOptions, BindgenOrchestrator
from mojo_bindgen.parsing.frontend import ClangOptions
from mojo_bindgen.parsing.parser import ParseError

stderr_console = Console(stderr=True)

LinkModeOption = Literal["external-call", "owned-dl-handle"]
DiagnosticsMode = Literal["text", "json", "silent"]


def _version_callback(value: bool) -> None:
    if value:
        sys.stdout.write(f"mojo-bindgen {__version__}\n")
        raise typer.Exit()


def run(
    header: Annotated[
        Path,
        typer.Argument(
            help=(
                "Primary C header. It drives default names and is included first when "
                "--public-header is used."
            )
        ),
    ],
    public_header: Annotated[
        list[Path] | None,
        typer.Option(
            "--public-header",
            metavar="PATH",
            help=(
                "Additional C header to include in the generated umbrella header. "
                "Repeat for sibling public headers"
            ),
            rich_help_panel="Input",
        ),
    ] = None,
    clang_arg: Annotated[
        list[str] | None,
        typer.Option(
            "--clang-arg",
            metavar="FLAG",
            help="Pass one raw flag to Clang unchanged after structured flags. Repeat as needed.",
            rich_help_panel="Clang",
        ),
    ] = None,
    include_dir: Annotated[
        list[Path] | None,
        typer.Option(
            "-I",
            "--include",
            metavar="PATH",
            help=(
                "Add a #include search directory for parsing, equivalent to Clang -I. "
                "Repeat as needed."
            ),
            rich_help_panel="Clang",
        ),
    ] = None,
    define: Annotated[
        list[str] | None,
        typer.Option(
            "-D",
            "--define",
            metavar="NAME[=VALUE]",
            help="Define a C preprocessor macro for parsing, equivalent to Clang -D.",
            rich_help_panel="Clang",
        ),
    ] = None,
    undefine: Annotated[
        list[str] | None,
        typer.Option(
            "-U",
            "--undefine",
            metavar="NAME",
            help="Undefine a C preprocessor macro for parsing, equivalent to Clang -U.",
            rich_help_panel="Clang",
        ),
    ] = None,
    sysroot: Annotated[
        Path | None,
        typer.Option(
            "--sysroot",
            metavar="PATH",
            help="Set the target sysroot for parsing, equivalent to Clang --sysroot.",
            rich_help_panel="Clang",
        ),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            metavar="TRIPLE",
            help="Set the target triple for parsing, equivalent to Clang --target.",
            rich_help_panel="Clang",
        ),
    ] = None,
    std: Annotated[
        str | None,
        typer.Option(
            "--std",
            metavar="STD",
            help="Set the C language standard for parsing, equivalent to Clang -std.",
            rich_help_panel="Clang",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Write primary output to this file (default: stdout).",
            show_default=False,
            rich_help_panel="Output",
        ),
    ] = None,
    layout_tests: Annotated[
        Path | None,
        typer.Option(
            "--layout-tests",
            metavar="PATH",
            help="Write a Mojo record-layout test sidecar to this path.",
            show_default=False,
            rich_help_panel="Output",
        ),
    ] = None,
    library: Annotated[
        str | None,
        typer.Option(
            "--library",
            metavar="NAME",
            help="Logical library/module name in generated metadata.",
            rich_help_panel="Linking",
        ),
    ] = None,
    link_name: Annotated[
        str | None,
        typer.Option(
            "--link-name",
            metavar="NAME",
            help="Native library name used for generated FFI calls.",
            rich_help_panel="Linking",
        ),
    ] = None,
    link_mode: Annotated[
        LinkModeOption,
        typer.Option(
            "--link-mode",
            help="Use external_call or runtime OwnedDLHandle symbol lookup.",
            case_sensitive=False,
            rich_help_panel="Linking",
        ),
    ] = "external-call",
    library_path: Annotated[
        str | None,
        typer.Option(
            "--library-path",
            metavar="PATH",
            help="Shared-library path candidate embedded for --link-mode owned-dl-handle.",
            rich_help_panel="Linking",
        ),
    ] = None,
    diagnostics: Annotated[
        DiagnosticsMode,
        typer.Option(
            "--diagnostics",
            help="Choose diagnostic output: text, json, or silent.",
            case_sensitive=False,
            rich_help_panel="Diagnostics",
        ),
    ] = "text",
    diagnostics_output: Annotated[
        Path | None,
        typer.Option(
            "--diagnostics-output",
            metavar="PATH",
            help="Write diagnostics to this path instead of stderr.",
            show_default=False,
            rich_help_panel="Diagnostics",
        ),
    ] = None,
    warnings_as_errors: Annotated[
        bool,
        typer.Option(
            "--warnings-as-errors",
            help="Exit nonzero after generation if any warning diagnostics are reported.",
            rich_help_panel="Diagnostics",
        ),
    ] = False,
    print_clang_args: Annotated[
        bool,
        typer.Option(
            "--print-clang-args",
            help="Print normalized Clang arguments and exit.",
            hidden=True,
        ),
    ] = False,
    dump_cir: Annotated[
        Path | None,
        typer.Option(
            "--dump-cir",
            metavar="PATH",
            help="Write raw parsed CIR JSON sidecar.",
            hidden=True,
        ),
    ] = None,
    dump_mojo_ir: Annotated[
        Path | None,
        typer.Option(
            "--dump-mojo-ir",
            metavar="PATH",
            help="Write finalized MojoIR JSON sidecar.",
            hidden=True,
        ),
    ] = None,
    dump_preprocessed: Annotated[
        Path | None,
        typer.Option(
            "--dump-preprocessed",
            metavar="PATH",
            help="Write Clang-preprocessed source sidecar.",
            hidden=True,
        ),
    ] = None,
    no_doc_comments: Annotated[
        bool,
        typer.Option(
            "--no-doc-comments",
            help="Do not emit captured C documentation comments into Mojo output.",
            rich_help_panel="Output",
        ),
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the mojo-bindgen version and exit.",
        ),
    ] = False,
) -> int:
    """Generate Mojo FFI from a C header using libclang.

    Examples:
      mojo-bindgen path/to/header.h -o bindings.mojo
      mojo-bindgen include/me.h --public-header include/me_extra.h -o out.mojo
      mojo-bindgen include/me.h -I ./include -D FEATURE=1 --std c11 -o out.mojo
      mojo-bindgen include/me.h --layout-tests layout_tests.mojo -o out.mojo

    The primary header and --public-header values are included in an internal
    umbrella header. Transitive #include files are parsed by Clang and may
    contribute declarations; no source-file filtering is applied yet.
    """
    clang_options = ClangOptions(
        std=std,
        target=target,
        sysroot=sysroot,
        include_dirs=tuple(include_dir or ()),
        defines=tuple(define or ()),
        undefines=tuple(undefine or ()),
        raw_args=tuple(clang_arg or ()),
    )
    options = BindgenOptions(
        header=header,
        include_headers=public_header,
        library=library,
        link_name=link_name,
        clang_options=clang_options,
        linking=_internal_link_mode(link_mode),
        library_path_hint=library_path,
        strict_abi=False,
        module_comment=True,
        emit_doc_comments=not no_doc_comments,
        layout_tests=layout_tests is not None,
        json_output=False,
        output=output,
        layout_test_output=layout_tests,
        clang_macro_fallback=False,
        clang_macro_fallback_build_dir=None,
        keep_going=False,
    )
    orchestrator = BindgenOrchestrator(options)

    if print_clang_args:
        sys.stdout.write(json.dumps(orchestrator.normalized_clang_args(), indent=2))
        sys.stdout.write("\n")
        return 0

    try:
        if dump_preprocessed is not None:
            _write_text(dump_preprocessed, orchestrator.dump_preprocessed())
        result = orchestrator.run()
    except (ParseError, FileNotFoundError, OSError, RuntimeError) as e:
        args = orchestrator.normalized_clang_args()
        stderr_console.print(
            "[bold red]mojo-bindgen error:[/bold red] "
            f"{e}\nprimary header: {header}\nclang args: {args}"
        )
        raise typer.Exit(code=1) from e

    _emit_diagnostics(
        result.unit.diagnostics,
        mode=diagnostics,
        output=diagnostics_output,
    )

    if dump_cir is not None:
        _write_text(dump_cir, result.unit.to_json())
    if dump_mojo_ir is not None:
        _write_text(dump_mojo_ir, result.mojo_module.to_json())

    text = result.bindings_source
    if output is None:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        _write_text(output, text)

    if result.layout_test_source is not None:
        sidecar = layout_tests
        if sidecar is not None:
            _write_text(sidecar, result.layout_test_source)

    if warnings_as_errors and any(d.severity == "warning" for d in result.unit.diagnostics):
        raise typer.Exit(code=1)
    return 0


def _internal_link_mode(link_mode: LinkModeOption) -> Literal["external_call", "owned_dl_handle"]:
    return "owned_dl_handle" if link_mode == "owned-dl-handle" else "external_call"


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _emit_diagnostics(
    diagnostics,
    *,
    mode: DiagnosticsMode,
    output: Path | None,
) -> None:
    if mode == "silent" or not diagnostics:
        return
    if mode == "json":
        payload = [
            {
                "stage": "frontend",
                "severity": d.severity,
                "message": d.message,
                "file": d.file,
                "line": d.line,
                "col": d.col,
                "decl_id": d.decl_id,
            }
            for d in diagnostics
        ]
        text = json.dumps(payload, indent=2)
    else:
        text = "\n".join(_format_diagnostic(d) for d in diagnostics)
    if output is not None:
        _write_text(output, text + "\n")
    else:
        stderr_console.print(text)


def _format_diagnostic(d) -> str:
    file = d.file or "<unknown>"
    line = d.line or 0
    col = d.col or 0
    return f"{file}:{line}:{col}: {d.severity}: {d.message}"


def main(argv: list[str] | None = None) -> int:
    cli_args = argv if argv is not None else sys.argv[1:]
    if not cli_args:
        cli_args = ["--help"]
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

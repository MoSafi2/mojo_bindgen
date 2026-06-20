"""Command-line interface for mojo-bindgen."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from mojo_bindgen.orchestrator import BindgenOptions, BindgenOrchestrator
from mojo_bindgen.parsing.frontend import ClangOptions
from mojo_bindgen.parsing.parser import ParseError

stderr_console = Console(stderr=True)

OutputFormat = Literal["mojo", "cir-json", "mojo-ir-json"]
LinkModeOption = Literal["external-call", "owned-dl-handle"]
DiagnosticsMode = Literal["text", "json", "silent"]


def run(
    header: Annotated[Path, typer.Argument(help="Path to the primary C header file")],
    emit_header: Annotated[
        list[Path] | None,
        typer.Option(
            "--emit-header",
            metavar="PATH",
            help=(
                "Additional public C header to emit from (repeatable). "
                "Private dependencies remain parsed but not emitted."
            ),
        ),
    ] = None,
    clang_arg: Annotated[
        list[str] | None,
        typer.Option(
            "--clang-arg",
            metavar="FLAG",
            help="Raw Clang flag escape hatch (repeatable).",
        ),
    ] = None,
    include_dir: Annotated[
        list[Path] | None,
        typer.Option("--include-dir", metavar="PATH", help="Add a Clang include directory."),
    ] = None,
    define: Annotated[
        list[str] | None,
        typer.Option("--define", metavar="NAME[=VALUE]", help="Define a C preprocessor macro."),
    ] = None,
    undefine: Annotated[
        list[str] | None,
        typer.Option("--undefine", metavar="NAME", help="Undefine a C preprocessor macro."),
    ] = None,
    sysroot: Annotated[
        Path | None,
        typer.Option("--sysroot", metavar="PATH", help="Set the Clang sysroot."),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option("--target", metavar="TRIPLE", help="Set the Clang target triple."),
    ] = None,
    std: Annotated[
        str | None,
        typer.Option("--std", metavar="STD", help="Set the C language standard."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write primary output to this file (default: stdout).",
            show_default=False,
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Primary output format.", case_sensitive=False),
    ] = "mojo",
    layout_test_output: Annotated[
        Path | None,
        typer.Option(
            "--layout-test-output",
            metavar="PATH",
            help="Write layout-test sidecar to this path.",
            show_default=False,
        ),
    ] = None,
    emit_layout_tests: Annotated[
        bool | None,
        typer.Option(
            "--emit-layout-tests/--no-emit-layout-tests",
            help="Write a Mojo record-layout test sidecar with file output.",
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
    link_mode: Annotated[
        LinkModeOption,
        typer.Option("--link-mode", help="FFI linking mode for Mojo output.", case_sensitive=False),
    ] = "external-call",
    library_path: Annotated[
        str | None,
        typer.Option(
            "--library-path",
            metavar="PATH",
            help="Shared-library candidate path for --link-mode owned-dl-handle.",
        ),
    ] = None,
    diagnostics: Annotated[
        DiagnosticsMode,
        typer.Option("--diagnostics", help="Diagnostic output mode.", case_sensitive=False),
    ] = "text",
    diagnostics_output: Annotated[
        Path | None,
        typer.Option(
            "--diagnostics-output",
            metavar="PATH",
            help="Write diagnostics to this path instead of stderr.",
            show_default=False,
        ),
    ] = None,
    warnings_as_errors: Annotated[
        bool,
        typer.Option("--warnings-as-errors", help="Exit nonzero when warnings are reported."),
    ] = False,
    keep_going: Annotated[
        bool,
        typer.Option("--keep-going", help="Emit partial artifacts when frontend errors permit it."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Run the pipeline without writing files."),
    ] = False,
    dump_clang_args: Annotated[
        bool,
        typer.Option("--dump-clang-args", help="Print normalized Clang arguments and exit."),
    ] = False,
    dump_cir: Annotated[
        Path | None,
        typer.Option("--dump-cir", metavar="PATH", help="Write raw parsed CIR JSON sidecar."),
    ] = None,
    dump_mojo_ir: Annotated[
        Path | None,
        typer.Option("--dump-mojo-ir", metavar="PATH", help="Write finalized MojoIR JSON sidecar."),
    ] = None,
    dump_preprocessed: Annotated[
        Path | None,
        typer.Option(
            "--dump-preprocessed",
            metavar="PATH",
            help="Write Clang-preprocessed source sidecar.",
        ),
    ] = None,
    doc_comments: Annotated[
        bool,
        typer.Option(
            "--doc-comments/--no-doc-comments",
            help="Emit captured C documentation comments into Mojo output.",
        ),
    ] = True,
    module_comment: Annotated[
        bool,
        typer.Option(
            "--module-comment/--no-module-comment",
            help="Emit generated-module header comments into Mojo output.",
        ),
    ] = True,
    strict_abi: Annotated[
        bool,
        typer.Option(
            "--strict-abi/--no-strict-abi",
            help="Preserve parsed C alignment emission behavior.",
        ),
    ] = False,
    clang_macro_fallback: Annotated[
        bool,
        typer.Option(
            "--clang-macro-fallback/--no-clang-macro-fallback",
            help="Evaluate unsupported object-like integer macros through Clang.",
        ),
    ] = False,
    clang_macro_fallback_dir: Annotated[
        Path | None,
        typer.Option(
            "--clang-macro-fallback-dir",
            metavar="PATH",
            help="Directory for temporary Clang macro fallback probe files.",
            show_default=False,
        ),
    ] = None,
) -> int:
    """Generate Mojo FFI from a C header using libclang.

    Examples:
      mojo-bindgen path/to/header.h --output bindings.mojo
      mojo-bindgen path/to/header.h --format cir-json --output unit.json
      mojo-bindgen include/me.h --emit-header include/me_extra.h --output out.mojo
      mojo-bindgen include/me.h --include-dir ./include --define FEATURE=1 --std c11
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
        include_headers=emit_header,
        library=library,
        link_name=link_name,
        clang_options=clang_options,
        linking=_internal_link_mode(link_mode),
        library_path_hint=library_path,
        strict_abi=strict_abi,
        module_comment=module_comment,
        emit_doc_comments=doc_comments,
        layout_tests=emit_layout_tests,
        json_output=output_format != "mojo",
        output=output,
        layout_test_output=layout_test_output,
        clang_macro_fallback=clang_macro_fallback,
        clang_macro_fallback_build_dir=clang_macro_fallback_dir,
        keep_going=keep_going,
    )
    orchestrator = BindgenOrchestrator(options)

    if dump_clang_args:
        sys.stdout.write(json.dumps(orchestrator.normalized_clang_args(), indent=2))
        sys.stdout.write("\n")
        return 0

    try:
        if dump_preprocessed is not None:
            _write_text(dump_preprocessed, orchestrator.dump_preprocessed(), dry_run=dry_run)
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
        dry_run=dry_run,
    )

    if dump_cir is not None:
        _write_text(dump_cir, result.unit.to_json(), dry_run=dry_run)
    if dump_mojo_ir is not None:
        _write_text(dump_mojo_ir, result.mojo_module.to_json(), dry_run=dry_run)

    text = _primary_output(result, output_format)
    if output is None:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        _write_text(output, text, dry_run=dry_run)

    if result.layout_test_source is not None:
        sidecar = layout_test_output
        if sidecar is None and output is not None:
            sidecar = output.with_name(f"{output.stem}_layout_tests.mojo")
        if sidecar is not None:
            _write_text(sidecar, result.layout_test_source, dry_run=dry_run)

    if warnings_as_errors and any(d.severity == "warning" for d in result.unit.diagnostics):
        raise typer.Exit(code=1)
    return 0


def _internal_link_mode(link_mode: LinkModeOption) -> Literal["external_call", "owned_dl_handle"]:
    return "owned_dl_handle" if link_mode == "owned-dl-handle" else "external_call"


def _primary_output(result, output_format: OutputFormat) -> str:
    if output_format == "cir-json":
        return result.unit.to_json()
    if output_format == "mojo-ir-json":
        return result.mojo_module.to_json()
    return result.bindings_source


def _write_text(path: Path, text: str, *, dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(text, encoding="utf-8")


def _emit_diagnostics(
    diagnostics,
    *,
    mode: DiagnosticsMode,
    output: Path | None,
    dry_run: bool,
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
        _write_text(output, text + "\n", dry_run=dry_run)
    else:
        stderr_console.print(text)


def _format_diagnostic(d) -> str:
    file = d.file or "<unknown>"
    line = d.line or 0
    col = d.col or 0
    return f"{file}:{line}:{col}: {d.severity}: {d.message}"


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

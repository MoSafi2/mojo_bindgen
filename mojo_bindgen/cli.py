"""Command-line interface for mojo-bindgen."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from mojo_bindgen import __version__
from mojo_bindgen._process import invoke, mojo_path

LinkModeOption = Literal["external-call", "owned-dl-handle"]
DiagnosticsMode = Literal["text", "json", "silent"]


def _version_callback(value: bool) -> None:
    if value:
        sys.stdout.write(f"mojo-bindgen {__version__}\n")
        raise typer.Exit()


def _mojo_path_callback(value: bool) -> None:
    if value:
        try:
            sys.stdout.write(str(mojo_path()) + "\n")
        except FileNotFoundError as error:
            Console(stderr=True).print(str(error), style="red", markup=False)
            raise typer.Exit(code=127) from error
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
    print_mojo_path: Annotated[
        bool,
        typer.Option(
            "--print-mojo-path",
            callback=_mojo_path_callback,
            is_eager=True,
            help="Print the installed public Mojo library import directory and exit.",
            rich_help_panel="Installation",
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
    # Generation and output decisions belong to the Mojo command. This layer only
    # translates the public presentation options and renders returned diagnostics.
    stderr_console = Console(stderr=True)
    arguments = [str(header)]
    for flag, values in (
        ("--public-header", public_header or ()),
        ("--clang-arg", clang_arg or ()),
        ("--include", include_dir or ()),
        ("--define", define or ()),
        ("--undefine", undefine or ()),
    ):
        for value in values:
            arguments.append(f"{flag}={value}")
    for flag, value in (
        ("--sysroot", sysroot),
        ("--target", target),
        ("--std", std),
        ("--output", output),
        ("--layout-tests", layout_tests),
        ("--library", library),
        ("--link-name", link_name),
        ("--link-mode", link_mode),
        ("--library-path", library_path),
        ("--dump-cir", dump_cir),
        ("--dump-mojo-ir", dump_mojo_ir),
        ("--dump-preprocessed", dump_preprocessed),
    ):
        if value is not None:
            arguments.append(f"{flag}={value}")
    for flag, value in (
        ("--warnings-as-errors", warnings_as_errors),
        ("--print-clang-args", print_clang_args),
        ("--no-doc-comments", no_doc_comments),
    ):
        if value:
            arguments.append(flag)
    with tempfile.TemporaryDirectory(prefix="mojo-bindgen-") as directory:
        collected = Path(directory) / "diagnostics.json"
        arguments += ["--diagnostics=json", f"--diagnostics-output={collected}"]
        try:
            completed = invoke(arguments)
        except KeyboardInterrupt as error:
            raise typer.Exit(code=130) from error
        except FileNotFoundError as error:
            stderr_console.print(str(error), style="red", markup=False)
            raise typer.Exit(code=127) from error
        except (OSError, RuntimeError) as error:
            stderr_console.print(str(error), style="red", markup=False)
            raise typer.Exit(code=126) from error
        sys.stdout.write(completed.stdout)
        if collected.exists() and diagnostics != "silent":
            entries = json.loads(collected.read_text(encoding="utf-8"))
            text = (
                json.dumps(entries, indent=2, ensure_ascii=False)
                if diagnostics == "json"
                else "\n".join(_format_diagnostic(d) for d in entries)
            ) + "\n"
            if diagnostics_output is not None:
                diagnostics_output.write_text(text, encoding="utf-8")
            elif diagnostics == "json":
                sys.stderr.write(text)
            else:
                for entry in entries:
                    style = {"warning": "yellow", "error": "red", "fatal": "red"}.get(
                        entry["severity"], "cyan"
                    )
                    stderr_console.print(
                        _format_diagnostic(entry), style=style, markup=False, highlight=False
                    )
        if completed.stderr:
            stderr_console.print(
                completed.stderr,
                end="",
                style="red" if completed.returncode else None,
                markup=False,
                highlight=False,
            )
        if completed.returncode:
            raise typer.Exit(code=completed.returncode)
    return 0


def _format_diagnostic(d: dict[str, object]) -> str:
    return (
        f"{d.get('file') or '<unknown>'}:{d.get('line') or 0}:{d.get('col') or 0}: "
        f"{d['severity']}: {d['message']}"
    )


app = typer.Typer(rich_markup_mode="rich")
app.command(name="mojo-bindgen")(run)


def main(argv: list[str] | None = None) -> int:
    cli_args = argv if argv is not None else sys.argv[1:]
    try:
        app(args=cli_args or ["--help"], prog_name="mojo-bindgen")
        return 0
    except typer.Exit as error:
        return error.exit_code
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

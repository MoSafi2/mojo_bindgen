"""Unit tests for the Typer-based CLI surface."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import mojo_bindgen.cli as cli

# Rich-styled Typer help embeds ANSI sequences; strip for stable substring checks.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;:]*m")


def _strip_ansi(s: str) -> str:
    return _ANSI_ESCAPE.sub("", s)


class _DummyUnit:
    diagnostics = []

    def to_json(self) -> str:
        return '{"ok": true}'


class _DummyMojoModule:
    def to_json(self) -> str:
        return '{"mojo": true}'


@dataclass(frozen=True)
class _DummyDiagnostic:
    severity: str
    message: str
    file: str | None = "demo.h"
    line: int | None = 1
    col: int | None = 2
    decl_id: str | None = None


def test_help_includes_examples(capsys) -> None:
    rc = cli.main(["--help"])
    captured = capsys.readouterr()
    assert rc == 0
    plain = _strip_ansi(captured.out)
    assert "Generate Mojo FFI" in plain
    assert "Examples:" in plain
    assert "--clang-arg" in plain


def test_no_args_prints_help_without_running_orchestrator(monkeypatch, capsys) -> None:
    def fail_orchestrator(_options):
        raise AssertionError("orchestrator should not be constructed")

    monkeypatch.setattr(cli, "BindgenOrchestrator", fail_orchestrator)

    rc = cli.main([])
    captured = capsys.readouterr()

    assert rc == 0
    plain = _strip_ansi(captured.out)
    assert "Generate Mojo FFI" in plain
    assert "Examples:" in plain


def test_version_prints_package_version_without_running_orchestrator(monkeypatch, capsys) -> None:
    def fail_orchestrator(_options):
        raise AssertionError("orchestrator should not be constructed")

    monkeypatch.setattr(cli, "BindgenOrchestrator", fail_orchestrator)

    rc = cli.main(["--version"])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == f"mojo-bindgen {cli.__version__}\n"


def test_cli_uses_orchestrator_and_stdout(monkeypatch, capsys, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    class DummyResult:
        unit = _DummyUnit()
        mojo_module = _DummyMojoModule()
        bindings_source = "generated"
        layout_test_source = None

    class DummyOrchestrator:
        def __init__(self, options) -> None:
            calls["options"] = options

        def normalized_clang_args(self):
            return self.run().unit.diagnostics

        def run(self) -> DummyResult:
            return DummyResult()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    header = tmp_path / "demo.h"
    extra = tmp_path / "extra.h"
    rc = cli.main(
        [
            str(header),
            "--public-header",
            str(extra),
            "--clang-arg=-Werror",
            "-I",
            "./include",
            "-D",
            "FEATURE=1",
            "-U",
            "OLD",
            "--std",
            "c11",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "generated\n"
    options = calls["options"]
    assert options.header == header
    assert options.include_headers == [extra]
    assert options.library is None
    assert options.link_name is None
    assert options.clang_options.to_args() == [
        "-x",
        "c",
        "-std=c11",
        "-Iinclude",
        "-DFEATURE=1",
        "-UOLD",
        "-Werror",
    ]
    assert options.json_output is False


def test_print_clang_args_prints_normalized_argv(monkeypatch, capsys, tmp_path: Path) -> None:
    class DummyOrchestrator:
        def __init__(self, options) -> None:
            self.options = options

        def normalized_clang_args(self):
            return self.options.clang_options.to_args()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    rc = cli.main(
        [
            str(tmp_path / "demo.h"),
            "--std",
            "c99",
            "--target",
            "x86_64-unknown-linux-gnu",
            "--sysroot",
            "/sdk",
            "--include",
            "/sdk/include",
            "--print-clang-args",
        ]
    )

    assert rc == 0
    assert '"-std=c99"' in capsys.readouterr().out


def test_mojo_mode_passes_emit_options(monkeypatch, capsys, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    class DummyResult:
        unit = _DummyUnit()
        mojo_module = _DummyMojoModule()
        bindings_source = "generated"
        layout_test_source = None

    class DummyOrchestrator:
        def __init__(self, options) -> None:
            calls["linking"] = options.linking
            calls["library_path_hint"] = options.library_path_hint
            calls["strict_abi"] = options.strict_abi
            calls["options"] = options

        def run(self) -> DummyResult:
            return DummyResult()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    header = tmp_path / "sample.h"
    rc = cli.main(
        [
            str(header),
            "--link-mode",
            "owned-dl-handle",
            "--library-path",
            "/tmp/libsample.so",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "generated\n"
    assert calls["linking"] == "owned_dl_handle"
    assert calls["library_path_hint"] == "/tmp/libsample.so"
    assert calls["strict_abi"] is False
    assert calls["options"].json_output is False
    assert calls["options"].module_comment is True


def test_output_mode_does_not_write_layout_test_sidecar_by_default(
    monkeypatch, tmp_path: Path
) -> None:
    class DummyResult:
        bindings_source = "bindings"
        layout_test_source = "layout tests"
        unit = _DummyUnit()
        mojo_module = _DummyMojoModule()

    class DummyOrchestrator:
        def __init__(self, _options) -> None:
            pass

        def run(self) -> DummyResult:
            return DummyResult()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    output = tmp_path / "demo_bindings.mojo"
    rc = cli.main([str(tmp_path / "demo.h"), "--output", str(output)])

    assert rc == 0
    assert output.read_text(encoding="utf-8") == "bindings"
    assert not (tmp_path / "demo_bindings_layout_tests.mojo").exists()


def test_layout_tests_writes_requested_sidecar(monkeypatch, tmp_path: Path) -> None:
    class DummyResult:
        bindings_source = "bindings"
        layout_test_source = "custom layout"
        unit = _DummyUnit()
        mojo_module = _DummyMojoModule()

    class DummyOrchestrator:
        def __init__(self, _options) -> None:
            pass

        def run(self) -> DummyResult:
            return DummyResult()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    output = tmp_path / "demo.mojo"
    sidecar = tmp_path / "checks.mojo"
    rc = cli.main(
        [
            str(tmp_path / "demo.h"),
            "--output",
            str(output),
            "--layout-tests",
            str(sidecar),
        ]
    )

    assert rc == 0
    assert sidecar.read_text(encoding="utf-8") == "custom layout"


def test_dump_sidecars(monkeypatch, tmp_path: Path) -> None:
    class DummyResult:
        bindings_source = "bindings"
        layout_test_source = None
        unit = _DummyUnit()
        mojo_module = _DummyMojoModule()

    class DummyOrchestrator:
        def __init__(self, _options) -> None:
            pass

        def run(self) -> DummyResult:
            return DummyResult()

        def dump_preprocessed(self) -> str:
            return "preprocessed"

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    output = tmp_path / "module.mojo"
    cir = tmp_path / "cir.json"
    mojo_ir = tmp_path / "mojo-ir.json"
    preprocessed = tmp_path / "demo.i"
    rc = cli.main(
        [
            str(tmp_path / "demo.h"),
            "--output",
            str(output),
            "--dump-cir",
            str(cir),
            "--dump-mojo-ir",
            str(mojo_ir),
            "--dump-preprocessed",
            str(preprocessed),
        ]
    )

    assert rc == 0
    assert output.read_text(encoding="utf-8") == "bindings"
    assert cir.read_text(encoding="utf-8") == '{"ok": true}'
    assert mojo_ir.read_text(encoding="utf-8") == '{"mojo": true}'
    assert preprocessed.read_text(encoding="utf-8") == "preprocessed"


def test_warnings_as_errors_exits_1_after_writing_outputs(monkeypatch, tmp_path: Path) -> None:
    class DummyUnit(_DummyUnit):
        diagnostics = [_DummyDiagnostic("warning", "careful")]

    class DummyResult:
        bindings_source = "bindings"
        layout_test_source = "layout"
        unit = DummyUnit()
        mojo_module = _DummyMojoModule()

    class DummyOrchestrator:
        def __init__(self, _options) -> None:
            pass

        def run(self) -> DummyResult:
            return DummyResult()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    output = tmp_path / "demo.mojo"
    diagnostics = tmp_path / "diagnostics.json"
    rc = cli.main(
        [
            str(tmp_path / "demo.h"),
            "--output",
            str(output),
            "--diagnostics",
            "json",
            "--diagnostics-output",
            str(diagnostics),
            "--warnings-as-errors",
        ]
    )

    assert rc == 1
    assert output.read_text(encoding="utf-8") == "bindings"
    assert diagnostics.exists()


def test_stdout_does_not_write_layout_tests_by_default(monkeypatch, capsys, tmp_path: Path) -> None:
    class DummyResult:
        unit = _DummyUnit()
        mojo_module = _DummyMojoModule()
        bindings_source = "bindings"
        layout_test_source = None

    class DummyOrchestrator:
        def __init__(self, _options) -> None:
            pass

        def run(self) -> DummyResult:
            return DummyResult()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    rc = cli.main([str(tmp_path / "demo.h")])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == "bindings\n"
    assert list(tmp_path.glob("*_layout_tests.mojo")) == []


def test_orchestrator_failures_return_exit_code_1(monkeypatch, capsys, tmp_path: Path) -> None:
    class DummyOrchestrator:
        def __init__(self, options) -> None:
            self.options = options

        def normalized_clang_args(self):
            return self.options.clang_options.to_args()

        def run(self):
            raise FileNotFoundError("header not found")

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    rc = cli.main([str(tmp_path / "missing.h")])
    captured = capsys.readouterr()
    assert rc == 1
    assert "mojo-bindgen error:" in captured.err
    assert "header not found" in captured.err
    assert "clang args:" in captured.err

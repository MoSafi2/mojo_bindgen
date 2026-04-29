"""Unit tests for the Typer-based CLI surface."""

from __future__ import annotations

import re
from pathlib import Path

import mojo_bindgen.cli as cli

# Rich-styled Typer help embeds ANSI sequences; strip for stable substring checks.
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;:]*m")


def _strip_ansi(s: str) -> str:
    return _ANSI_ESCAPE.sub("", s)


class _DummyUnit:
    def to_json(self) -> str:
        return '{"ok": true}'


def test_help_includes_examples(capsys) -> None:
    rc = cli.main(["--help"])
    captured = capsys.readouterr()
    assert rc == 0
    plain = _strip_ansi(captured.out)
    assert "Generate Mojo FFI" in plain
    assert "Examples:" in plain
    assert "--compile-arg" in plain


def test_json_mode_uses_orchestrator_and_stdout(monkeypatch, capsys, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    class DummyResult:
        unit = _DummyUnit()
        bindings_source = "generated"
        layout_test_source = None

    class DummyOrchestrator:
        def __init__(self, options) -> None:
            calls["options"] = options

        def run(self) -> DummyResult:
            return DummyResult()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    header = tmp_path / "demo.h"
    rc = cli.main([str(header), "--json", "--compile-arg=-I./include"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == '{"ok": true}\n'
    options = calls["options"]
    assert options.header == header
    assert options.library is None
    assert options.link_name is None
    assert options.compile_args == ["-I./include"]
    assert options.json_output is True


def test_non_json_mode_passes_emit_options(monkeypatch, capsys, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    class DummyResult:
        unit = _DummyUnit()
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
            "--linking",
            "owned_dl_handle",
            "--library-path-hint",
            "/tmp/libsample.so",
            "--strict-abi",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "generated\n"
    assert calls["linking"] == "owned_dl_handle"
    assert calls["library_path_hint"] == "/tmp/libsample.so"
    assert calls["strict_abi"] is True
    assert calls["options"].json_output is False


def test_output_mode_writes_default_layout_test_sidecar(monkeypatch, tmp_path: Path) -> None:
    class DummyResult:
        bindings_source = "bindings"
        layout_test_source = "layout tests"
        unit = _DummyUnit()

    class DummyOrchestrator:
        def __init__(self, _options) -> None:
            pass

        def run(self) -> DummyResult:
            return DummyResult()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    output = tmp_path / "demo_bindings.mojo"
    rc = cli.main([str(tmp_path / "demo.h"), "-o", str(output)])

    assert rc == 0
    assert output.read_text(encoding="utf-8") == "bindings"
    assert (tmp_path / "demo_bindings_test.mojo").read_text(encoding="utf-8") == "layout tests"


def test_no_layout_tests_suppresses_default_sidecar(monkeypatch, tmp_path: Path) -> None:
    class DummyResult:
        unit = _DummyUnit()
        bindings_source = "bindings"
        layout_test_source = None

    class DummyOrchestrator:
        def __init__(self, _options) -> None:
            pass

        def run(self) -> DummyResult:
            return DummyResult()

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    output = tmp_path / "demo.mojo"
    rc = cli.main([str(tmp_path / "demo.h"), "-o", str(output), "--no-layout-tests"])

    assert rc == 0
    assert output.read_text(encoding="utf-8") == "bindings"
    assert not (tmp_path / "demo_test.mojo").exists()


def test_custom_layout_test_output_writes_requested_sidecar(monkeypatch, tmp_path: Path) -> None:
    class DummyResult:
        bindings_source = "bindings"
        layout_test_source = "custom layout"
        unit = _DummyUnit()

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
            "-o",
            str(output),
            "--layout-test-output",
            str(sidecar),
        ]
    )

    assert rc == 0
    assert sidecar.read_text(encoding="utf-8") == "custom layout"


def test_stdout_does_not_write_layout_tests_by_default(monkeypatch, capsys, tmp_path: Path) -> None:
    class DummyResult:
        unit = _DummyUnit()
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
    assert list(tmp_path.glob("*_test.mojo")) == []


def test_orchestrator_failures_return_exit_code_1(monkeypatch, capsys, tmp_path: Path) -> None:
    class DummyOrchestrator:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def run(self):
            raise FileNotFoundError("header not found")

    monkeypatch.setattr(cli, "BindgenOrchestrator", DummyOrchestrator)

    rc = cli.main([str(tmp_path / "missing.h")])
    captured = capsys.readouterr()
    assert rc == 1
    assert "mojo-bindgen error:" in captured.err
    assert "header not found" in captured.err

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


def test_json_mode_uses_parser_and_stdout(monkeypatch, capsys, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    class DummyParser:
        def __init__(
            self,
            header: Path,
            *,
            library: str,
            link_name: str,
            compile_args: list[str] | None,
            raise_on_error: bool,
        ) -> None:
            calls["header"] = header
            calls["library"] = library
            calls["link_name"] = link_name
            calls["compile_args"] = compile_args
            calls["raise_on_error"] = raise_on_error

        def run(self) -> _DummyUnit:
            return _DummyUnit()

    monkeypatch.setattr(cli, "ClangParser", DummyParser)

    header = tmp_path / "demo.h"
    rc = cli.main([str(header), "--json", "--compile-arg=-I./include"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == '{"ok": true}\n'
    assert calls == {
        "header": header,
        "library": "demo",
        "link_name": "demo",
        "compile_args": ["-I./include"],
        "raise_on_error": True,
    }


def test_non_json_mode_passes_emit_options(monkeypatch, capsys, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    class DummyParser:
        def __init__(
            self,
            *_args: object,
            **_kwargs: object,
        ) -> None:
            pass

        def run(self) -> _DummyUnit:
            return _DummyUnit()

    class DummyGenerator:
        def __init__(self, opts) -> None:
            calls["linking"] = opts.linking
            calls["library_path_hint"] = opts.library_path_hint
            calls["strict_abi"] = opts.strict_abi

        def generate(self, _unit: _DummyUnit) -> str:
            return "generated"

    monkeypatch.setattr(cli, "ClangParser", DummyParser)
    monkeypatch.setattr(cli, "MojoGenerator", DummyGenerator)

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
    assert calls == {
        "linking": "owned_dl_handle",
        "library_path_hint": "/tmp/libsample.so",
        "strict_abi": True,
    }


def test_output_mode_writes_default_layout_test_sidecar(monkeypatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    class DummyArtifacts:
        bindings_source = "bindings"
        layout_test_source = "layout tests"

    class DummyParser:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def run(self) -> _DummyUnit:
            return _DummyUnit()

    class DummyGenerator:
        def __init__(self, _opts) -> None:
            pass

        def generate_artifacts(self, _unit, *, layout_tests: bool, main_module_name: str):
            calls["layout_tests"] = layout_tests
            calls["main_module_name"] = main_module_name
            return DummyArtifacts()

    monkeypatch.setattr(cli, "ClangParser", DummyParser)
    monkeypatch.setattr(cli, "MojoGenerator", DummyGenerator)

    output = tmp_path / "demo_bindings.mojo"
    rc = cli.main([str(tmp_path / "demo.h"), "-o", str(output)])

    assert rc == 0
    assert output.read_text(encoding="utf-8") == "bindings"
    assert (tmp_path / "demo_bindings_test.mojo").read_text(encoding="utf-8") == "layout tests"
    assert calls == {"layout_tests": True, "main_module_name": "demo_bindings"}


def test_no_layout_tests_suppresses_default_sidecar(monkeypatch, tmp_path: Path) -> None:
    class DummyParser:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def run(self) -> _DummyUnit:
            return _DummyUnit()

    class DummyGenerator:
        def __init__(self, _opts) -> None:
            pass

        def generate(self, _unit: _DummyUnit) -> str:
            return "bindings"

    monkeypatch.setattr(cli, "ClangParser", DummyParser)
    monkeypatch.setattr(cli, "MojoGenerator", DummyGenerator)

    output = tmp_path / "demo.mojo"
    rc = cli.main([str(tmp_path / "demo.h"), "-o", str(output), "--no-layout-tests"])

    assert rc == 0
    assert output.read_text(encoding="utf-8") == "bindings"
    assert not (tmp_path / "demo_test.mojo").exists()


def test_custom_layout_test_output_writes_requested_sidecar(monkeypatch, tmp_path: Path) -> None:
    class DummyArtifacts:
        bindings_source = "bindings"
        layout_test_source = "custom layout"

    class DummyParser:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def run(self) -> _DummyUnit:
            return _DummyUnit()

    class DummyGenerator:
        def __init__(self, _opts) -> None:
            pass

        def generate_artifacts(self, _unit, *, layout_tests: bool, main_module_name: str):
            assert layout_tests is True
            assert main_module_name == "demo"
            return DummyArtifacts()

    monkeypatch.setattr(cli, "ClangParser", DummyParser)
    monkeypatch.setattr(cli, "MojoGenerator", DummyGenerator)

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
    class DummyParser:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def run(self) -> _DummyUnit:
            return _DummyUnit()

    class DummyGenerator:
        def __init__(self, _opts) -> None:
            pass

        def generate(self, _unit: _DummyUnit) -> str:
            return "bindings"

    monkeypatch.setattr(cli, "ClangParser", DummyParser)
    monkeypatch.setattr(cli, "MojoGenerator", DummyGenerator)

    rc = cli.main([str(tmp_path / "demo.h")])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == "bindings\n"
    assert list(tmp_path.glob("*_test.mojo")) == []


def test_parser_failures_return_exit_code_1(monkeypatch, capsys, tmp_path: Path) -> None:
    class DummyParser:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def run(self):
            raise FileNotFoundError("header not found")

    monkeypatch.setattr(cli, "ClangParser", DummyParser)

    rc = cli.main([str(tmp_path / "missing.h")])
    captured = capsys.readouterr()
    assert rc == 1
    assert "mojo-bindgen error:" in captured.err
    assert "header not found" in captured.err

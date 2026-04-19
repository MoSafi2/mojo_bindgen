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
            calls["emit_align"] = opts.emit_align

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
            "--no-emit-align",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "generated\n"
    assert calls == {
        "linking": "owned_dl_handle",
        "library_path_hint": "/tmp/libsample.so",
        "emit_align": False,
    }


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

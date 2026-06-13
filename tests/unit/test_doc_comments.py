"""Tests for source documentation comment capture and emission."""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.mojo_ir_printer import _clean_doc_comment
from mojo_bindgen.ir import DocComment, Enum, Function, GlobalVar, Struct
from mojo_bindgen.parsing.parser import ClangParser
from tests.bindgen_helpers import MojoGenerator


def _has_libclang() -> bool:
    try:
        import clang.cindex  # noqa: F401
    except ImportError:
        return False
    return True


def test_clean_doc_comment_strips_common_c_doc_markers() -> None:
    doc = DocComment(
        text="""/**
         * Adds two values.
         *
         * @return the total
         */"""
    )

    assert _clean_doc_comment(doc) == [
        "Adds two values.",
        "",
        "@return the total",
    ]


def test_clean_doc_comment_strips_line_doc_markers() -> None:
    doc = DocComment(
        text="""/// First line.
///   Indented detail."""
    )

    assert _clean_doc_comment(doc) == ["First line.", "  Indented detail."]


@pytest.mark.skipif(not _has_libclang(), reason="libclang not available (use pixi run)")
def test_parser_captures_docs_on_public_declarations(tmp_path: Path) -> None:
    header = tmp_path / "docs.h"
    header.write_text(
        """
/** A documented struct. */
struct Widget {
    /// Field count.
    int count;
};

/** Mode enum. */
enum Mode {
    /// Ready state.
    MODE_READY = 1,
};

/** Adds two integers. */
int add(int lhs, int rhs);

/** External value. */
extern const int VALUE;
""",
        encoding="utf-8",
    )

    unit = ClangParser(header, library="docs", link_name="docs", compile_args=[]).run()

    struct = next(decl for decl in unit.decls if isinstance(decl, Struct))
    enum = next(decl for decl in unit.decls if isinstance(decl, Enum))
    function = next(decl for decl in unit.decls if isinstance(decl, Function))
    global_var = next(decl for decl in unit.decls if isinstance(decl, GlobalVar))

    assert struct.doc is not None
    assert "documented struct" in struct.doc.text
    assert struct.fields[0].doc is not None
    assert "Field count" in struct.fields[0].doc.text
    assert enum.doc is not None
    assert enum.enumerants[0].doc is not None
    assert function.doc is not None
    assert global_var.doc is not None


@pytest.mark.skipif(not _has_libclang(), reason="libclang not available (use pixi run)")
def test_mojo_emits_docs_and_respects_disable_option(tmp_path: Path) -> None:
    header = tmp_path / "docs.h"
    header.write_text(
        """
/** A documented struct. */
struct Widget {
    /// Field count.
    int count;
};

/** Adds two integers. */
int add(int lhs, int rhs);
""",
        encoding="utf-8",
    )
    unit = ClangParser(header, library="docs", link_name="docs", compile_args=[]).run()

    rendered = MojoGenerator().generate(unit)
    assert '"""' in rendered
    assert "A documented struct." in rendered
    assert "# Field count." in rendered
    assert "Adds two integers." in rendered

    disabled = MojoGenerator(MojoEmitOptions(emit_doc_comments=False)).generate(unit)
    assert "A documented struct." not in disabled
    assert "Field count." not in disabled
    assert "Adds two integers." not in disabled

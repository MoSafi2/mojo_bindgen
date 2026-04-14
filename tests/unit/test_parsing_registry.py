"""Tests for parser frontend and declaration registry services."""

from __future__ import annotations

from pathlib import Path

import pytest
import clang.cindex as cx

from mojo_bindgen.parsing.frontend import ClangFrontend, ClangFrontendConfig
from mojo_bindgen.parsing.registry import DeclRegistry


def _has_libclang() -> bool:
    try:
        import clang.cindex  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _has_libclang(),
    reason="libclang not available (use pixi run)",
)


def test_registry_unifies_forward_decl_and_definition(tmp_path: Path) -> None:
    header = tmp_path / "registry_forward.h"
    header.write_text(
        (
            "struct node;\n"
            "struct node { int value; };\n"
        ),
        encoding="utf-8",
    )

    frontend = ClangFrontend(ClangFrontendConfig(header=header, compile_args=()))
    tu = frontend.parse_translation_unit()
    registry = DeclRegistry.build_from_translation_unit(tu, frontend)

    records = [
        cursor
        for cursor in frontend.iter_primary_cursors(tu)
        if cursor.spelling == "node"
    ]
    assert len(records) == 2
    assert registry.decl_id_for_cursor(records[0]) == registry.decl_id_for_cursor(records[1])
    assert registry.is_complete_record_decl(records[0]) is True


def test_registry_synthesizes_anonymous_record_identity(tmp_path: Path) -> None:
    header = tmp_path / "registry_anon.h"
    header.write_text(
        "struct outer { struct { int x; } inner; };\n",
        encoding="utf-8",
    )

    frontend = ClangFrontend(ClangFrontendConfig(header=header, compile_args=()))
    tu = frontend.parse_translation_unit()
    registry = DeclRegistry.build_from_translation_unit(tu, frontend)

    outer = next(
        cursor
        for cursor in frontend.iter_primary_cursors(tu)
        if cursor.kind == cx.CursorKind.STRUCT_DECL and cursor.spelling == "outer"
    )
    inner_field = next(
        child
        for child in outer.get_children()
        if child.kind == cx.CursorKind.FIELD_DECL and child.spelling == "inner"
    )
    anonymous = inner_field.type.get_canonical().get_declaration().get_definition()
    decl_id, name, c_name, is_anonymous = registry.record_identity(anonymous)
    assert decl_id
    assert name.startswith("__bindgen_anon_")
    assert c_name == name
    assert is_anonymous is True

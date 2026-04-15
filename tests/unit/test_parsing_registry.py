"""Tests for parser frontend and declaration registry services."""

from __future__ import annotations

from pathlib import Path

import pytest
import clang.cindex as cx

from mojo_bindgen.parsing.frontend import ClangFrontend, ClangFrontendConfig
from mojo_bindgen.parsing.index import DeclIndex


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
    registry =  DeclIndex.build_from_translation_unit(tu, frontend)

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
    registry = DeclIndex.build_from_translation_unit(tu, frontend)

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
    assert name.startswith("outer__anon_struct_1")
    assert c_name == name
    assert is_anonymous is True
    assert "/" not in name
    assert ":" not in name


def test_registry_distinguishes_sibling_anonymous_record_definitions(tmp_path: Path) -> None:
    header = tmp_path / "registry_nested_anon.h"
    header.write_text(
        (
            "struct outer {\n"
            "  union {\n"
            "    struct { int x; int y; };\n"
            "    struct { float u; float v; };\n"
            "  };\n"
            "};\n"
        ),
        encoding="utf-8",
    )

    frontend = ClangFrontend(ClangFrontendConfig(header=header, compile_args=()))
    tu = frontend.parse_translation_unit()
    registry = DeclIndex.build_from_translation_unit(tu, frontend)

    outer = next(
        cursor
        for cursor in frontend.iter_primary_cursors(tu)
        if cursor.kind == cx.CursorKind.STRUCT_DECL and cursor.spelling == "outer"
    )
    anon_union = next(
        child
        for child in outer.get_children()
        if child.kind == cx.CursorKind.UNION_DECL and child.is_definition()
    )
    anon_structs = [
        child
        for child in anon_union.get_children()
        if child.kind == cx.CursorKind.STRUCT_DECL and child.is_definition()
    ]

    assert len(anon_structs) == 2
    assert anon_structs[0].get_usr() == anon_structs[1].get_usr()
    assert registry.decl_id_for_cursor(anon_structs[0]) != registry.decl_id_for_cursor(anon_structs[1])

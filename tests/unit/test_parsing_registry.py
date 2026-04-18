"""Tests for parser frontend and declaration registry services."""

from __future__ import annotations

from pathlib import Path

import pytest
import clang.cindex as cx
from mojo_bindgen.ir import Struct

from mojo_bindgen.parsing.frontend import ClangFrontend, ClangFrontendConfig
from mojo_bindgen.parsing.registry import RecordRegistry


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
    registry =  RecordRegistry.build_from_translation_unit(tu, frontend)

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
    registry = RecordRegistry.build_from_translation_unit(tu, frontend)

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
    decl_id = registry.decl_id_for_cursor(anonymous)
    naming = registry.record_naming(anonymous)
    assert decl_id
    assert naming.name.startswith("outer__anon_struct_1")
    assert naming.c_name == naming.name
    assert naming.is_anonymous is True
    assert "/" not in naming.name
    assert ":" not in naming.name


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
    registry = RecordRegistry.build_from_translation_unit(tu, frontend)

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


def test_registry_prefers_cached_lowered_record_over_nominal_resolution(tmp_path: Path) -> None:
    header = tmp_path / "registry_cache.h"
    header.write_text(
        "struct node { int value; };\n",
        encoding="utf-8",
    )

    frontend = ClangFrontend(ClangFrontendConfig(header=header, compile_args=()))
    tu = frontend.parse_translation_unit()
    registry = RecordRegistry.build_from_translation_unit(tu, frontend)

    node = next(
        cursor
        for cursor in frontend.iter_primary_cursors(tu)
        if cursor.kind == cx.CursorKind.STRUCT_DECL and cursor.spelling == "node"
    )
    cached = Struct(
        decl_id=registry.decl_id_for_cursor(node),
        name="node_cached",
        c_name="node_cached",
        fields=[],
        size_bytes=max(0, node.type.get_size()),
        align_bytes=max(1, node.type.get_align()),
        is_union=False,
    )
    registry.store(cached)

    lowered = registry.lower_record_type(node.type)
    assert lowered.name == "node_cached"
    assert lowered.decl_id == cached.decl_id

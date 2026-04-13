"""Tests for context-aware type lowering through ClangParser."""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.ir import EnumRef, Function, Pointer, Primitive, Struct, StructRef, TypeRef
from mojo_bindgen.parsing.field_builder import FieldBuildResult
from mojo_bindgen.parsing.parser import ClangParser
from mojo_bindgen.parsing.struct_builder import StructBuildResult


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


def test_builder_result_contracts_are_internal_and_simple() -> None:
    s = Struct(name="x", c_name="x", fields=[], size_bytes=0, align_bytes=1)
    fb = FieldBuildResult(field=None, nested=[s])
    sb = StructBuildResult(struct=s, nested=[s])
    assert fb.field is None
    assert fb.nested[0].name == "x"
    assert sb.struct.c_name == "x"
    assert sb.nested[0].align_bytes == 1


def test_type_context_field_param_return_typedef(tmp_path: Path) -> None:
    header = tmp_path / "type_builder_ctx.h"
    header.write_text(
        (
            "typedef unsigned int my_uint;\n"
            "typedef enum mode_t { MODE_A = 1 } mode_t;\n"
            "typedef struct payload_t {\n"
            "  my_uint value;\n"
            "  mode_t mode;\n"
            "} payload_t;\n"
            "mode_t take_mode(my_uint input);\n"
        ),
        encoding="utf-8",
    )
    parser = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    )
    unit = parser.run()

    payload = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "payload_t")
    fn = next(d for d in unit.decls if isinstance(d, Function) and d.name == "take_mode")

    # FIELD context: typedefs lower to canonical representation.
    assert isinstance(payload.fields[0].type, Primitive)
    assert payload.fields[0].type.name == "unsigned int"
    assert isinstance(payload.fields[1].type, EnumRef)
    assert payload.fields[1].type.name == "mode_t"

    # PARAM / RETURN context: typedef names are preserved as TypeRef.
    assert isinstance(fn.ret, TypeRef)
    assert fn.ret.name == "mode_t"
    assert isinstance(fn.ret.canonical, EnumRef)
    assert isinstance(fn.params[0].type, TypeRef)
    assert fn.params[0].type.name == "my_uint"
    assert isinstance(fn.params[0].type.canonical, Primitive)


def test_struct_builder_handles_nested_anon_and_bitfields(tmp_path: Path) -> None:
    header = tmp_path / "struct_builder_nested.h"
    header.write_text(
        (
            "struct outer_t {\n"
            "  struct { int x; } nested_struct;\n"
            "  union { int y; float z; } nested_union;\n"
            "  unsigned int flags:3;\n"
            "  unsigned int :0;\n"
            "};\n"
            "typedef struct outer_t outer_t;\n"
        ),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    outer = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "outer_t")

    nested_struct_field = next(f for f in outer.fields if f.name == "nested_struct")
    assert isinstance(nested_struct_field.type, StructRef)
    assert nested_struct_field.type.is_union is False

    nested_union_field = next(f for f in outer.fields if f.name == "nested_union")
    assert isinstance(nested_union_field.type, StructRef)
    assert nested_union_field.type.is_union is True
    assert nested_union_field.type.size_bytes > 0

    flags = next(f for f in outer.fields if f.name == "flags")
    assert flags.is_bitfield
    assert flags.bit_width == 3
    assert isinstance(flags.type, Primitive)

    zero_width = next(f for f in outer.fields if f.name == "")
    assert zero_width.is_bitfield
    assert zero_width.bit_width == 0


def test_struct_builder_handles_recursive_pointer_to_self(tmp_path: Path) -> None:
    header = tmp_path / "struct_builder_recursive.h"
    header.write_text(
        (
            "struct node {\n"
            "  int value;\n"
            "  struct node* next;\n"
            "};\n"
            "typedef struct node node;\n"
        ),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    node = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "node")
    next_field = next(f for f in node.fields if f.name == "next")
    assert isinstance(next_field.type, Pointer)
    assert isinstance(next_field.type.pointee, StructRef)
    assert next_field.type.pointee.name == "node"

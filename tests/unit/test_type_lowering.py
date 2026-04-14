"""Tests for context-aware parser type lowering through `ClangParser`."""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.ir import EnumRef, Function, Pointer, Primitive, Struct, StructRef, TypeRef
from mojo_bindgen.parsing.lowering import TypeContext
from mojo_bindgen.parsing.parser import ClangParser


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


def test_type_context_enum_is_stable() -> None:
    assert isinstance(TypeContext.FIELD, TypeContext)
    assert isinstance(TypeContext.PARAM, TypeContext)
    assert isinstance(TypeContext.RETURN, TypeContext)
    assert isinstance(TypeContext.TYPEDEF, TypeContext)


def test_type_lowering_preserves_typedefs_by_context(tmp_path: Path) -> None:
    header = tmp_path / "type_lowering_ctx.h"
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
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    payload = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "payload_t")
    fn = next(d for d in unit.decls if isinstance(d, Function) and d.name == "take_mode")

    assert isinstance(payload.fields[0].type, Primitive)
    assert payload.fields[0].type.name == "unsigned int"
    assert isinstance(payload.fields[1].type, EnumRef)
    assert payload.fields[1].type.name == "mode_t"

    assert isinstance(fn.ret, TypeRef)
    assert fn.ret.name == "mode_t"
    assert isinstance(fn.ret.canonical, EnumRef)
    assert isinstance(fn.params[0].type, TypeRef)
    assert fn.params[0].type.name == "my_uint"
    assert isinstance(fn.params[0].type.canonical, Primitive)



def test_record_lowering_handles_nested_anon_and_bitfields(tmp_path: Path) -> None:
    header = tmp_path / "record_lowering_nested.h"
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


def test_record_lowering_handles_recursive_pointer_to_self(tmp_path: Path) -> None:
    header = tmp_path / "record_lowering_recursive.h"
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

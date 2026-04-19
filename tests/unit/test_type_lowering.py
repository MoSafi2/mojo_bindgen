"""Tests for context-aware parser type lowering through `ClangParser`."""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.codegen.generator import MojoGenerator
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    AtomicType,
    EnumRef,
    Function,
    FunctionPtr,
    IntKind,
    IntType,
    Pointer,
    QualifiedType,
    Struct,
    StructRef,
    Typedef,
    TypeRef,
    VectorType,
)
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

    assert isinstance(payload.fields[0].type, TypeRef)
    assert payload.fields[0].type.name == "my_uint"
    assert isinstance(payload.fields[0].type.canonical, IntType)
    assert payload.fields[0].type.canonical.size_bytes == 4
    assert isinstance(payload.fields[1].type, TypeRef)
    assert payload.fields[1].type.name == "mode_t"
    assert isinstance(payload.fields[1].type.canonical, EnumRef)
    assert payload.fields[1].type.canonical.name == "mode_t"

    assert isinstance(fn.ret, TypeRef)
    assert fn.ret.name == "mode_t"
    assert isinstance(fn.ret.canonical, EnumRef)
    assert isinstance(fn.params[0].type, TypeRef)
    assert fn.params[0].type.name == "my_uint"
    assert isinstance(fn.params[0].type.canonical, IntType)


def test_type_lowering_preserves_callback_parameter_names_across_positions(tmp_path: Path) -> None:
    header = tmp_path / "callback_param_names.h"
    header.write_text(
        (
            "typedef int (*typedef_cb_t)(int value, void *userdata);\n"
            "struct callbacks_t {\n"
            "  int (*poll)(int timeout_ms, void *);\n"
            "};\n"
            "int install(int (*fn)(int count, void *ctx));\n"
            "int (*chooser(void))(int timeout_ms, void *userdata);\n"
        ),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    typedef_cb = next(d for d in unit.decls if isinstance(d, Typedef) and d.name == "typedef_cb_t")
    callbacks = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "callbacks_t")
    install = next(d for d in unit.decls if isinstance(d, Function) and d.name == "install")
    chooser = next(d for d in unit.decls if isinstance(d, Function) and d.name == "chooser")

    assert isinstance(typedef_cb.aliased, FunctionPtr)
    assert typedef_cb.aliased.param_names == ["value", "userdata"]

    poll = next(f for f in callbacks.fields if f.name == "poll")
    assert isinstance(poll.type, FunctionPtr)
    assert poll.type.param_names == ["timeout_ms", ""]

    assert isinstance(install.params[0].type, FunctionPtr)
    assert install.params[0].type.param_names == ["count", "ctx"]

    assert isinstance(chooser.ret, FunctionPtr)
    assert chooser.ret.param_names == ["timeout_ms", "userdata"]


def test_codegen_preserves_callback_parameter_names_and_falls_back_for_unnamed(
    tmp_path: Path,
) -> None:
    header = tmp_path / "callback_codegen_names.h"
    header.write_text(
        (
            "typedef int (*named_cb_t)(int value, void *userdata);\n"
            "struct callbacks_t {\n"
            "  int (*poll)(int timeout_ms, void *);\n"
            "};\n"
        ),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    out = MojoGenerator(MojoEmitOptions()).generate(unit)

    assert (
        'comptime named_cb_t = def (value: c_int, userdata: MutOpaquePointer[MutExternalOrigin]) thin abi("C") -> c_int'
        in out
    )
    assert (
        'comptime callbacks_t_poll_cb = def (timeout_ms: c_int, arg1: MutOpaquePointer[MutExternalOrigin]) thin abi("C") -> c_int'
        in out
    )


def test_type_lowering_fully_canonicalizes_nested_typedef_chain(tmp_path: Path) -> None:
    header = tmp_path / "nested_typedef_chain.h"
    header.write_text(
        (
            "typedef unsigned int inner_t;\n"
            "typedef inner_t outer_t;\n"
            "typedef struct payload_t {\n"
            "  outer_t value;\n"
            "} payload_t;\n"
        ),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    outer = next(d for d in unit.decls if isinstance(d, Typedef) and d.name == "outer_t")
    payload = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "payload_t")

    assert isinstance(outer.aliased, TypeRef)
    assert outer.aliased.name == "inner_t"
    assert isinstance(outer.canonical, IntType)
    assert isinstance(payload.fields[0].type, TypeRef)
    assert payload.fields[0].type.name == "outer_t"
    assert isinstance(payload.fields[0].type.canonical, IntType)


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
    assert isinstance(flags.type, IntType)

    zero_width = next(f for f in outer.fields if f.name == "")
    assert zero_width.is_bitfield
    assert zero_width.bit_width == 0


def test_record_lowering_preserves_direct_anonymous_record_members(tmp_path: Path) -> None:
    header = tmp_path / "record_lowering_direct_anon.h"
    header.write_text(
        (
            "struct outer_t {\n"
            "  int tag;\n"
            "  union {\n"
            "    struct { int x; int y; };\n"
            "    int flat;\n"
            "  };\n"
            "};\n"
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
    anon_union = next(f for f in outer.fields if f.is_anonymous and isinstance(f.type, StructRef))
    assert anon_union.byte_offset == 4
    assert anon_union.type.is_union is True
    assert anon_union.type.is_anonymous is True

    inner_union = next(
        d for d in unit.decls if isinstance(d, Struct) and d.decl_id == anon_union.type.decl_id
    )
    anon_struct = next(
        f for f in inner_union.fields if f.is_anonymous and isinstance(f.type, StructRef)
    )
    assert anon_struct.byte_offset == 0
    assert anon_struct.type.is_union is False
    assert anon_struct.type.is_anonymous is True

    leaf_struct = next(
        d for d in unit.decls if isinstance(d, Struct) and d.decl_id == anon_struct.type.decl_id
    )
    assert [f.name for f in leaf_struct.fields] == ["x", "y"]


def test_codegen_emits_synthesized_fields_for_direct_anonymous_members(tmp_path: Path) -> None:
    header = tmp_path / "record_codegen_direct_anon.h"
    header.write_text(
        ("typedef struct outer_t {\n  int tag;\n  union {\n    int value;\n  };\n} outer_t;\n"),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    out = MojoGenerator(MojoEmitOptions()).generate(unit)

    assert "struct outer_t" in out
    assert "var tag: c_int" in out
    assert "var _anon_1: " in out
    assert "struct __bindgen_anon_" not in out


def test_record_lowering_handles_recursive_pointer_to_self(tmp_path: Path) -> None:
    header = tmp_path / "record_lowering_recursive.h"
    header.write_text(
        ("struct node {\n  int value;\n  struct node* next;\n};\ntypedef struct node node;\n"),
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


def test_type_lowering_preserves_qualified_atomic_pointee(tmp_path: Path) -> None:
    header = tmp_path / "qualified_atomic_ptr.h"
    header.write_text(
        "int ev_load_atomic(const _Atomic int *src);\n",
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    fn = next(d for d in unit.decls if isinstance(d, Function) and d.name == "ev_load_atomic")
    assert isinstance(fn.params[0].type, Pointer)
    assert isinstance(fn.params[0].type.pointee, QualifiedType)
    assert fn.params[0].type.pointee.qualifiers.is_const is True
    assert isinstance(fn.params[0].type.pointee.unqualified, AtomicType)
    assert isinstance(fn.params[0].type.pointee.unqualified.value_type, IntType)
    assert fn.params[0].type.pointee.unqualified.value_type.int_kind == IntKind.INT


def test_type_lowering_recovers_vector_lane_count_for_vector_size_typedef(tmp_path: Path) -> None:
    header = tmp_path / "vector_size_typedef.h"
    header.write_text(
        (
            "typedef float vet_float4 __attribute__((vector_size(16)));\n"
            "typedef struct vet_payload { vet_float4 lanes; } vet_payload;\n"
        ),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    td = next(d for d in unit.decls if isinstance(d, Typedef) and d.name == "vet_float4")
    payload = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "vet_payload")

    assert isinstance(td.canonical, VectorType)
    assert td.canonical.count == 4
    assert isinstance(payload.fields[0].type, TypeRef)
    assert payload.fields[0].type.name == "vet_float4"
    assert isinstance(payload.fields[0].type.canonical, VectorType)
    assert payload.fields[0].type.canonical.count == 4

    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert "from std.builtin.simd import SIMD" in out
    assert "comptime vet_float4 = SIMD[DType.float32, 4]" in out


def test_record_lowering_emits_named_nested_record_defs_for_pointer_fields(tmp_path: Path) -> None:
    header = tmp_path / "record_lowering_named_nested_ptr.h"
    header.write_text(
        ("struct outer {\n  struct inner {\n    int x;\n  } *p;\n  struct inner *q;\n};\n"),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    outer = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "outer")
    inner = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "inner")

    p_field = next(f for f in outer.fields if f.name == "p")
    q_field = next(f for f in outer.fields if f.name == "q")
    assert isinstance(p_field.type, Pointer)
    assert isinstance(p_field.type.pointee, StructRef)
    assert p_field.type.pointee.decl_id == inner.decl_id
    assert isinstance(q_field.type, Pointer)
    assert isinstance(q_field.type.pointee, StructRef)
    assert q_field.type.pointee.decl_id == inner.decl_id


def test_record_lowering_emits_named_nested_record_defs_for_value_fields(tmp_path: Path) -> None:
    header = tmp_path / "record_lowering_named_nested_value.h"
    header.write_text(
        ("struct outer {\n  struct inner_value {\n    int y;\n  } value;\n};\n"),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    outer = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "outer")
    inner = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "inner_value")

    value_field = next(f for f in outer.fields if f.name == "value")
    assert isinstance(value_field.type, StructRef)
    assert value_field.type.decl_id == inner.decl_id


def test_record_lowering_reuses_named_nested_record_nominally_after_definition(
    tmp_path: Path,
) -> None:
    header = tmp_path / "record_lowering_named_nested_nominal.h"
    header.write_text(
        (
            "struct outer {\n"
            "  struct inner_value {\n"
            "    int y;\n"
            "  } value;\n"
            "  struct inner_value copy;\n"
            "};\n"
        ),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    outer = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "outer")
    inner = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "inner_value")

    copy_field = next(f for f in outer.fields if f.name == "copy")
    assert isinstance(copy_field.type, StructRef)
    assert copy_field.type.decl_id == inner.decl_id
    assert copy_field.type.name == "inner_value"
    assert copy_field.type.is_anonymous is False


def test_codegen_emits_named_nested_record_defs_before_parent(tmp_path: Path) -> None:
    header = tmp_path / "record_codegen_named_nested.h"
    header.write_text(
        (
            "struct sqlite3_index_info {\n"
            "  struct sqlite3_index_constraint { int iColumn; } *aConstraint;\n"
            "  struct sqlite3_index_orderby { int desc; } *aOrderBy;\n"
            "  struct sqlite3_index_constraint_usage { int argvIndex; } *aConstraintUsage;\n"
            "};\n"
        ),
        encoding="utf-8",
    )
    unit = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    ).run()

    out = MojoGenerator(MojoEmitOptions()).generate(unit)

    assert "struct sqlite3_index_constraint" in out
    assert "struct sqlite3_index_orderby" in out
    assert "struct sqlite3_index_constraint_usage" in out
    assert "struct sqlite3_index_info" in out
    assert out.index("struct sqlite3_index_constraint") < out.index("struct sqlite3_index_info")
    assert "var aConstraint: UnsafePointer[sqlite3_index_constraint, MutExternalOrigin]" in out
    assert "var aOrderBy: UnsafePointer[sqlite3_index_orderby, MutExternalOrigin]" in out
    assert (
        "var aConstraintUsage: UnsafePointer[sqlite3_index_constraint_usage, MutExternalOrigin]"
        in out
    )

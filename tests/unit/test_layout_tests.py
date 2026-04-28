"""Tests for generated Mojo record-layout test sidecars."""

from __future__ import annotations

from mojo_bindgen.ir import ByteOrder, Field, IntKind, IntType, Struct, TargetABI, Unit
from mojo_bindgen.layout_tests import collect_layout_record_checks, render_layout_test_module
from mojo_bindgen.mojo_ir import (
    BitfieldField,
    BitfieldGroupMember,
    BuiltinType,
    LinkMode,
    MojoBuiltin,
    MojoModule,
    OpaqueStorageMember,
    StoredMember,
    StructDecl,
    StructKind,
)


def _abi() -> TargetABI:
    return TargetABI(
        pointer_size_bytes=8,
        pointer_align_bytes=8,
        byte_order=ByteOrder.LITTLE,
    )


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _u8() -> IntType:
    return IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1)


def _unit(*decls: Struct) -> Unit:
    return Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=list(decls),
    )


def _module(*decls: StructDecl) -> MojoModule:
    return MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
        decls=list(decls),
    )


def test_collect_layout_record_checks_for_plain_struct_with_padding() -> None:
    decl = Struct(
        decl_id="struct:Sample",
        name="Sample",
        c_name="Sample",
        fields=[
            Field(name="a", source_name="a", type=_u8(), byte_offset=0, size_bytes=1),
            Field(name="b", source_name="b", type=_i32(), byte_offset=4, size_bytes=4),
        ],
        size_bytes=8,
        align_bytes=4,
    )
    mojo_decl = StructDecl(
        name="Sample",
        members=[
            StoredMember(0, "a", BuiltinType(MojoBuiltin.C_UCHAR), 0),
            OpaqueStorageMember("__pad0", 3),
            StoredMember(1, "b", BuiltinType(MojoBuiltin.C_INT), 4),
        ],
    )

    checks = collect_layout_record_checks(
        normalized_unit=_unit(decl),
        mojo_module=_module(mojo_decl),
    )

    assert checks[0].record_name == "Sample"
    assert [(check.label, check.expected) for check in checks[0].checks] == [
        ("Sample.size", 8),
        ("Sample.align", 4),
        ("Sample.a.offset", 0),
        ("Sample.b.offset", 4),
    ]


def test_collect_layout_record_checks_for_opaque_storage_skips_field_offsets() -> None:
    decl = Struct(
        decl_id="struct:Packed",
        name="Packed",
        c_name="Packed",
        fields=[Field(name="x", source_name="x", type=_i32(), byte_offset=1, size_bytes=4)],
        size_bytes=5,
        align_bytes=1,
        is_packed=True,
    )
    mojo_decl = StructDecl(
        name="Packed",
        members=[OpaqueStorageMember("storage", 5)],
    )

    checks = collect_layout_record_checks(
        normalized_unit=_unit(decl),
        mojo_module=_module(mojo_decl),
    )

    assert [(check.label, check.expected) for check in checks[0].checks] == [
        ("Packed.size", 5),
        ("Packed.align", 1),
    ]


def test_collect_layout_record_checks_for_bitfield_storage_group_offset() -> None:
    decl = Struct(
        decl_id="struct:Flags",
        name="Flags",
        c_name="Flags",
        fields=[
            Field(
                name="enabled",
                source_name="enabled",
                type=_i32(),
                byte_offset=0,
                size_bytes=4,
                is_bitfield=True,
                bit_offset=0,
                bit_width=1,
            )
        ],
        size_bytes=4,
        align_bytes=4,
    )
    mojo_decl = StructDecl(
        name="Flags",
        members=[
            BitfieldGroupMember(
                storage_name="__bf0",
                storage_type=BuiltinType(MojoBuiltin.C_UINT),
                byte_offset=0,
                first_index=0,
                storage_width_bits=32,
                fields=[
                    BitfieldField(
                        index=0,
                        name="enabled",
                        logical_type=BuiltinType(MojoBuiltin.C_INT),
                        bit_offset=0,
                        bit_width=1,
                        signed=True,
                    )
                ],
            )
        ],
    )

    checks = collect_layout_record_checks(
        normalized_unit=_unit(decl),
        mojo_module=_module(mojo_decl),
    )

    assert ("Flags.__bf0.offset", 0) in [
        (check.label, check.expected) for check in checks[0].checks
    ]
    assert all("enabled.offset" not in check.label for check in checks[0].checks)


def test_collect_layout_record_checks_skips_incomplete_union_and_enum_structs() -> None:
    incomplete = Struct(
        decl_id="struct:Forward",
        name="Forward",
        c_name="Forward",
        fields=[],
        size_bytes=0,
        align_bytes=0,
        is_complete=False,
    )
    union = Struct(
        decl_id="union:Payload",
        name="Payload",
        c_name="Payload",
        fields=[Field(name="x", source_name="x", type=_i32(), byte_offset=0, size_bytes=4)],
        size_bytes=4,
        align_bytes=4,
        is_union=True,
    )
    enum_struct = StructDecl(name="Forward", kind=StructKind.ENUM)

    assert (
        collect_layout_record_checks(
            normalized_unit=_unit(incomplete, union),
            mojo_module=_module(enum_struct),
        )
        == ()
    )


def test_render_layout_test_module_imports_records_and_calls_tests() -> None:
    decl = Struct(
        decl_id="struct:Sample",
        name="Sample",
        c_name="Sample",
        fields=[Field(name="x", source_name="x", type=_i32(), byte_offset=0, size_bytes=4)],
        size_bytes=4,
        align_bytes=4,
    )
    mojo_decl = StructDecl(
        name="Sample",
        members=[StoredMember(0, "x", BuiltinType(MojoBuiltin.C_INT), 0)],
    )

    out = render_layout_test_module(
        normalized_unit=_unit(decl),
        mojo_module=_module(mojo_decl),
        main_module_name="bindings",
    )

    assert "from std.sys.info import align_of, size_of" in out
    assert "from std.reflection import offset_of" in out
    assert "from bindings import Sample" in out
    assert "def test_layout_Sample() raises:" in out
    assert 'offset_of[Sample, name="x"]()' in out
    assert "def main() raises:\n    test_layout_Sample()" in out

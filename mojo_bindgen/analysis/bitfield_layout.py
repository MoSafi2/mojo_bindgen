"""Pure CIR bitfield storage grouping and semantics."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.lowering_support import field_display_name
from mojo_bindgen.analysis.type_layout import peel_layout_wrappers
from mojo_bindgen.ir import Field, IntKind, IntType, Struct


@dataclass(frozen=True)
class BitfieldMemberLayout:
    index: int
    field: Field
    bit_offset: int
    bit_width: int
    signed: bool
    bool_semantics: bool


@dataclass(frozen=True)
class BitfieldRunLayout:
    name: str
    first_index: int
    byte_offset: int
    start_bit: int
    storage_width_bits: int
    unsigned_storage_type: IntType
    members: tuple[BitfieldMemberLayout, ...]

    @property
    def size_bytes(self) -> int:
        return self.storage_width_bits // 8

    @property
    def align_bytes(self) -> int:
        return self.unsigned_storage_type.align_bytes or self.unsigned_storage_type.size_bytes


@dataclass
class _BitfieldRunBuilder:
    name: str
    first_index: int
    byte_offset: int
    start_bit: int
    storage_width_bits: int
    unsigned_storage_type: IntType
    members: list[BitfieldMemberLayout]


def analyze_bitfield_layout(
    decl: Struct,
) -> tuple[tuple[BitfieldRunLayout, ...], tuple[str, ...]]:
    """Compute bitfield storage runs and structural problems for one struct."""

    builders: list[_BitfieldRunBuilder] = []
    problems: list[str] = []
    current: _BitfieldRunBuilder | None = None

    for index, field in enumerate(decl.fields):
        if not field.is_bitfield:
            current = None
            continue

        field_name = field_display_name(field, index)
        width_bits = bitfield_storage_width_bits(field)
        unsigned_storage_type = bitfield_unsigned_storage_type(field)
        if width_bits is None or unsigned_storage_type is None:
            problems.append(f"bitfield `{field_name}` has unsupported backing storage")
            current = None
            continue

        if field.bit_width == 0:
            current = None
            continue

        field_end_bit = field.bit_offset + field.bit_width
        needs_new_storage = True
        if current is not None:
            widened_width_bits = max(current.storage_width_bits, width_bits)
            needs_new_storage = (
                field.bit_offset < current.start_bit
                or field_end_bit > current.start_bit + widened_width_bits
            )

        active_run: _BitfieldRunBuilder
        if needs_new_storage:
            storage_start_bit = (field.bit_offset // width_bits) * width_bits
            active_run = _BitfieldRunBuilder(
                name=f"__bf{len(builders)}",
                first_index=index,
                byte_offset=storage_start_bit // 8,
                start_bit=storage_start_bit,
                storage_width_bits=width_bits,
                unsigned_storage_type=unsigned_storage_type,
                members=[],
            )
            builders.append(active_run)
            current = active_run
        elif current is not None:
            active_run = current
            if width_bits > active_run.storage_width_bits:
                active_run.storage_width_bits = width_bits
                active_run.unsigned_storage_type = unsigned_storage_type
        else:
            continue

        if field.is_anonymous:
            continue

        active_run.members.append(
            BitfieldMemberLayout(
                index=index,
                field=field,
                bit_offset=field.bit_offset,
                bit_width=field.bit_width,
                signed=bitfield_field_is_signed(field),
                bool_semantics=bitfield_field_is_bool(field),
            )
        )

    return (
        tuple(
            BitfieldRunLayout(
                name=builder.name,
                first_index=builder.first_index,
                byte_offset=builder.byte_offset,
                start_bit=builder.start_bit,
                storage_width_bits=builder.storage_width_bits,
                unsigned_storage_type=builder.unsigned_storage_type,
                members=tuple(builder.members),
            )
            for builder in builders
        ),
        tuple(problems),
    )


def bitfield_storage_width_bits(field: Field) -> int | None:
    core = peel_layout_wrappers(field.type)
    if not isinstance(core, IntType):
        return None
    return core.size_bytes * 8 if core.size_bytes > 0 else None


def bitfield_field_is_signed(field: Field) -> bool:
    core = peel_layout_wrappers(field.type)
    if not isinstance(core, IntType):
        return False
    return core.int_kind not in {
        IntKind.BOOL,
        IntKind.CHAR_U,
        IntKind.UCHAR,
        IntKind.USHORT,
        IntKind.UINT,
        IntKind.ULONG,
        IntKind.ULONGLONG,
        IntKind.UINT128,
        IntKind.CHAR16,
        IntKind.CHAR32,
    }


def bitfield_field_is_bool(field: Field) -> bool:
    core = peel_layout_wrappers(field.type)
    return isinstance(core, IntType) and core.int_kind == IntKind.BOOL


def bitfield_unsigned_storage_type(field: Field) -> IntType | None:
    core = peel_layout_wrappers(field.type)
    if not isinstance(core, IntType):
        return None
    unsigned_kind = {
        IntKind.BOOL: IntKind.UCHAR,
        IntKind.CHAR_S: IntKind.CHAR_U,
        IntKind.CHAR_U: IntKind.CHAR_U,
        IntKind.SCHAR: IntKind.UCHAR,
        IntKind.UCHAR: IntKind.UCHAR,
        IntKind.SHORT: IntKind.USHORT,
        IntKind.USHORT: IntKind.USHORT,
        IntKind.INT: IntKind.UINT,
        IntKind.UINT: IntKind.UINT,
        IntKind.LONG: IntKind.ULONG,
        IntKind.ULONG: IntKind.ULONG,
        IntKind.LONGLONG: IntKind.ULONGLONG,
        IntKind.ULONGLONG: IntKind.ULONGLONG,
        IntKind.INT128: IntKind.UINT128,
        IntKind.UINT128: IntKind.UINT128,
        IntKind.WCHAR: IntKind.WCHAR,
        IntKind.CHAR16: IntKind.CHAR16,
        IntKind.CHAR32: IntKind.CHAR32,
        IntKind.EXT_INT: IntKind.EXT_INT,
    }.get(core.int_kind)
    if unsigned_kind is None:
        return None
    return IntType(
        int_kind=unsigned_kind,
        size_bytes=core.size_bytes,
        align_bytes=core.align_bytes,
        ext_bits=core.ext_bits,
    )

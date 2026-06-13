"""Pure CIR bitfield storage grouping and semantics."""

from __future__ import annotations

from dataclasses import dataclass, field

from mojo_bindgen.analysis.facts.type_layout import peel_layout_wrappers
from mojo_bindgen.analysis.mojo.lowering_support import field_display_name
from mojo_bindgen.ir import Field, IntKind, IntType, Struct, Type


@dataclass(frozen=True)
class BitfieldFieldLayout:
    index: int
    field: Field
    logical_type: Type
    bit_offset: int
    bit_width: int
    signed: bool
    bool_semantics: bool


@dataclass
class BitfieldRunLayout:
    name: str
    first_index: int
    byte_offset: int
    start_bit: int
    storage_width_bits: int
    unsigned_storage_type: IntType
    fields: list[BitfieldFieldLayout] = field(default_factory=list)

    @property
    def size_bytes(self) -> int:
        return self.storage_width_bits // 8

    @property
    def align_bytes(self) -> int:
        return self.unsigned_storage_type.align_bytes or self.unsigned_storage_type.size_bytes


@dataclass(frozen=True)
class _BitfieldStorage:
    width_bits: int
    unsigned_type: IntType


def analyze_bitfield_layout(
    decl: Struct,
) -> tuple[tuple[BitfieldRunLayout, ...], tuple[str, ...]]:
    """Compute bitfield storage runs and structural problems for one struct."""

    runs: list[BitfieldRunLayout] = []
    problems: list[str] = []
    current: BitfieldRunLayout | None = None

    for index, _field in enumerate(decl.fields):
        if not _field.is_bitfield:
            current = None
            continue

        field_name = field_display_name(_field, index)
        storage = _bitfield_storage(_field)
        if storage is None:
            problems.append(f"bitfield `{field_name}` has unsupported backing storage")
            current = None
            continue

        if _field.bit_width == 0:
            current = None
            continue

        current = _select_bitfield_run(
            runs,
            current=current,
            field=_field,
            index=index,
            storage=storage,
        )
        _append_named_bitfield(current, field=_field, index=index)

    return tuple(runs), tuple(problems)


def _bitfield_storage(field: Field) -> _BitfieldStorage | None:
    width_bits = bitfield_storage_width_bits(field)
    unsigned_storage_type = bitfield_unsigned_storage_type(field)
    if width_bits is None or unsigned_storage_type is None:
        return None
    return _BitfieldStorage(width_bits=width_bits, unsigned_type=unsigned_storage_type)


def _select_bitfield_run(
    runs: list[BitfieldRunLayout],
    *,
    current: BitfieldRunLayout | None,
    field: Field,
    index: int,
    storage: _BitfieldStorage,
) -> BitfieldRunLayout:
    if current is None or _needs_new_storage_run(current, field=field, storage=storage):
        storage_start_bit = (field.bit_offset // storage.width_bits) * storage.width_bits
        current = BitfieldRunLayout(
            name=f"__bf{len(runs)}",
            first_index=index,
            byte_offset=storage_start_bit // 8,
            start_bit=storage_start_bit,
            storage_width_bits=storage.width_bits,
            unsigned_storage_type=storage.unsigned_type,
        )
        runs.append(current)
        return current

    if storage.width_bits > current.storage_width_bits:
        current.storage_width_bits = storage.width_bits
        current.unsigned_storage_type = storage.unsigned_type
    return current


def _needs_new_storage_run(
    current: BitfieldRunLayout,
    *,
    field: Field,
    storage: _BitfieldStorage,
) -> bool:
    field_end_bit = field.bit_offset + field.bit_width
    widened_width_bits = max(current.storage_width_bits, storage.width_bits)
    return (
        field.bit_offset < current.start_bit
        or field_end_bit > current.start_bit + widened_width_bits
    )


def _append_named_bitfield(
    current: BitfieldRunLayout,
    *,
    field: Field,
    index: int,
) -> None:
    if field.is_anonymous:
        return
    current.fields.append(
        BitfieldFieldLayout(
            index=index,
            field=field,
            logical_type=field.type,
            bit_offset=field.bit_offset,
            bit_width=field.bit_width,
            signed=bitfield_field_is_signed(field),
            bool_semantics=bitfield_field_is_bool(field),
        )
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
    return core.int_kind not in _UNSIGNED_OR_BOOL_INT_KINDS


def bitfield_field_is_bool(field: Field) -> bool:
    core = peel_layout_wrappers(field.type)
    return isinstance(core, IntType) and core.int_kind == IntKind.BOOL


def bitfield_unsigned_storage_type(field: Field) -> IntType | None:
    core = peel_layout_wrappers(field.type)
    if not isinstance(core, IntType):
        return None
    unsigned_kind = _UNSIGNED_STORAGE_KIND_BY_INT_KIND.get(core.int_kind)
    if unsigned_kind is None:
        return None
    return IntType(
        int_kind=unsigned_kind,
        size_bytes=core.size_bytes,
        align_bytes=core.align_bytes,
        ext_bits=core.ext_bits,
    )


_UNSIGNED_OR_BOOL_INT_KINDS = {
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

_UNSIGNED_STORAGE_KIND_BY_INT_KIND: dict[IntKind, IntKind] = {
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
}


__all__ = [
    "BitfieldFieldLayout",
    "BitfieldRunLayout",
    "analyze_bitfield_layout",
    "bitfield_field_is_bool",
    "bitfield_field_is_signed",
    "bitfield_storage_width_bits",
    "bitfield_unsigned_storage_type",
]

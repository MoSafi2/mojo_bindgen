from std.memory import ArcPointer
from ...ir import *
from .type_layout import peel_layout_wrappers
from ..mojo.mapping_support import field_display_name


@fieldwise_init
struct BitfieldFieldLayout(Copyable, Movable):
    var index: Int
    var field: Field
    var logical_type: ArcPointer[CType]
    var bit_offset: Int
    var bit_width: Int
    var signed: Bool
    var bool_semantics: Bool


@fieldwise_init
struct BitfieldRunLayout(Copyable, Movable):
    var name: String
    var first_index: Int
    var byte_offset: Int
    var start_bit: Int
    var storage_width_bits: Int
    var unsigned_storage_type: IntType
    var fields: List[BitfieldFieldLayout]

    def size_bytes(self) -> Int:
        return self.storage_width_bits // 8

    def align_bytes(self) -> Int:
        return (
            self.unsigned_storage_type.align_bytes.value() if self.unsigned_storage_type.align_bytes
            and self.unsigned_storage_type.align_bytes.value()
            != 0 else self.unsigned_storage_type.size_bytes
        )


def bitfield_field_is_signed(field: Field) -> Bool:
    var core = peel_layout_wrappers(field.type.ptr()[])
    match core:
        case .int_type(v):
            match v.int_kind:
                case .BOOL | .CHAR_U | .UCHAR | .USHORT | .UINT | .ULONG | .ULONGLONG | .UINT128 | .CHAR16 | .CHAR32:
                    return False
                case _:
                    return True
        case _:
            return False


def bitfield_field_is_bool(field: Field) -> Bool:
    var core = peel_layout_wrappers(field.type.ptr()[])
    match core:
        case .int_type(v):
            return v.int_kind == IntKind.BOOL
        case _:
            return False


def bitfield_unsigned_storage_type(field: Field) -> Optional[IntType]:
    var core = peel_layout_wrappers(field.type.ptr()[])
    match core:
        case .int_type(v):
            var result = v.copy()
            match v.int_kind:
                case .BOOL | .UCHAR | .SCHAR:
                    result.int_kind = IntKind.UCHAR
                case .CHAR_S | .CHAR_U:
                    result.int_kind = IntKind.CHAR_U
                case .SHORT | .USHORT:
                    result.int_kind = IntKind.USHORT
                case .INT | .UINT:
                    result.int_kind = IntKind.UINT
                case .LONG | .ULONG:
                    result.int_kind = IntKind.ULONG
                case .LONGLONG | .ULONGLONG:
                    result.int_kind = IntKind.ULONGLONG
                case .INT128 | .UINT128:
                    result.int_kind = IntKind.UINT128
                case _:
                    pass
            return result^
        case _:
            return {}


def analyze_bitfield_layout(decl: Struct) -> Tuple[List[BitfieldRunLayout], List[String]]:
    var runs = List[BitfieldRunLayout]()
    var problems = List[String]()
    var current = -1
    for index in range(len(decl.fields)):
        var field = decl.fields[index].copy()
        if not field.is_bitfield:
            current = -1
            continue
        var storage = bitfield_unsigned_storage_type(field)
        if not storage or storage.value().size_bytes <= 0:
            problems.append(
                "bitfield `"
                + field_display_name(field, index)
                + "` has unsupported backing storage"
            )
            current = -1
            continue
        if field.bit_width == 0:
            current = -1
            continue
        var width = storage.value().size_bytes * 8
        var new_run = current < 0
        if current >= 0:
            new_run = field.bit_offset < runs[
                current
            ].start_bit or field.bit_offset + field.bit_width > runs[current].start_bit + max(
                width, runs[current].storage_width_bits
            )
        if new_run:
            var start = (field.bit_offset // width) * width
            runs.append(
                BitfieldRunLayout(
                    "__bf" + String(len(runs)),
                    index,
                    start // 8,
                    start,
                    width,
                    storage.value().copy(),
                    List[BitfieldFieldLayout](),
                )
            )
            current = len(runs) - 1
        elif width > runs[current].storage_width_bits:
            runs[current].storage_width_bits = width
            runs[current].unsigned_storage_type = storage.value().copy()
        if not field.is_anonymous:
            runs[current].fields.append(
                BitfieldFieldLayout(
                    index,
                    field.copy(),
                    field.type.copy(),
                    field.bit_offset,
                    field.bit_width,
                    bitfield_field_is_signed(field),
                    bitfield_field_is_bool(field),
                )
            )
    return (runs^, problems^)

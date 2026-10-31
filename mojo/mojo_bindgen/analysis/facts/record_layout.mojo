from ...ir import *
from .type_layout import type_align
from .bitfield_layout import BitfieldRunLayout, analyze_bitfield_layout
from ..mojo.mapping_support import field_display_name


@fieldwise_init
struct PlainFieldFact(Copyable, Movable):
    var index: Int
    var byte_offset: Int
    var size_bytes: Int
    var align_bytes: Int


@fieldwise_init
struct PaddingSpan(Copyable, Movable):
    var name: String
    var byte_offset: Int
    var size_bytes: Int


@fieldwise_init
struct _LayoutItem(Copyable, Movable):
    var index: Int
    var byte_offset: Int
    var size_bytes: Int
    var align_bytes: Int


struct RecordLayoutFacts(Copyable, Movable):
    var is_complete: Bool
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var is_packed: Bool
    var requested_align_bytes: Optional[Int]
    var natural_typed_align_bytes: Optional[Int]
    var plain_fields: List[PlainFieldFact]
    var bitfield_runs: List[BitfieldRunLayout]
    var padding_spans: List[PaddingSpan]
    var layout_problems: List[String]

    def __init__(out self):
        self.is_complete = False
        self.size_bytes = 0
        self.align_bytes = {}
        self.is_packed = False
        self.requested_align_bytes = {}
        self.natural_typed_align_bytes = {}
        self.plain_fields = List[PlainFieldFact]()
        self.bitfield_runs = List[BitfieldRunLayout]()
        self.padding_spans = List[PaddingSpan]()
        self.layout_problems = List[String]()

    def is_pure_bitfield(self) -> Bool:
        return len(self.bitfield_runs) != 0 and len(self.plain_fields) == 0


def align_up(offset: Int, align: Int) -> Int:
    if align <= 1:
        return offset
    var rem = offset % align
    return offset if rem == 0 else offset + align - rem


def analyze_record_layout(decl: Struct) -> RecordLayoutFacts:
    var result = RecordLayoutFacts()
    result.size_bytes = decl.size_bytes
    result.is_packed = decl.is_packed
    result.requested_align_bytes = decl.requested_align_bytes
    if not decl.is_complete:
        return result^
    result.is_complete = True
    result.align_bytes = decl.align_bytes
    for i in range(len(decl.fields)):
        var f = decl.fields[i].copy()
        if f.is_bitfield:
            continue
        var align = type_align(f.type.ptr()[])
        var allowed = False
        match f.type.ptr()[]:
            case .c_array(_) | .struct_ref(_):
                allowed = True
            case _:
                pass
        if not align or (f.size_bytes <= 0 and not allowed):
            result.layout_problems.append(
                "field `" + field_display_name(f, i) + "` has unsupported layout metadata"
            )
            continue
        result.plain_fields.append(PlainFieldFact(i, f.byte_offset, f.size_bytes, align.value()))
    var bitfields = analyze_bitfield_layout(decl)
    result.bitfield_runs = bitfields[0].copy()
    result.layout_problems.extend(bitfields[1].copy())
    var items = List[_LayoutItem]()
    var natural_align = 1
    for f in result.plain_fields:
        natural_align = max(natural_align, f.align_bytes)
        items.append(_LayoutItem(f.index, f.byte_offset, f.size_bytes, f.align_bytes))
    for run in result.bitfield_runs:
        natural_align = max(natural_align, run.align_bytes())
        items.append(
            _LayoutItem(run.first_index, run.byte_offset, run.size_bytes(), run.align_bytes())
        )
    result.natural_typed_align_bytes = natural_align
    for i in range(1, len(items)):
        var j = i
        while j > 0 and (
            items[j].byte_offset < items[j - 1].byte_offset
            or (
                items[j].byte_offset == items[j - 1].byte_offset
                and items[j].index < items[j - 1].index
            )
        ):
            var temporary = items[j].copy()
            items[j] = items[j - 1].copy()
            items[j - 1] = temporary^
            j -= 1
    var current = 0
    var layout_problems = List[String]()
    for item in items:
        var natural = align_up(current, item.align_bytes)
        if item.byte_offset < natural:
            layout_problems.append(
                "member at byte offset "
                + String(item.byte_offset)
                + " is before the natural typed offset "
                + String(natural)
            )
            continue
        if item.align_bytes > 1 and item.byte_offset % item.align_bytes != 0:
            layout_problems.append(
                "member at byte offset "
                + String(item.byte_offset)
                + " is not representable with typed alignment "
                + String(item.align_bytes)
            )
            continue
        if item.byte_offset > natural:
            result.padding_spans.append(
                PaddingSpan(
                    "__pad" + String(len(result.padding_spans)), natural, item.byte_offset - natural
                )
            )
        current = item.byte_offset + item.size_bytes
    var end = align_up(current, decl.align_bytes)
    if end > decl.size_bytes:
        layout_problems.append(
            "typed members consume "
            + String(end)
            + " bytes after struct alignment, exceeding C size "
            + String(decl.size_bytes)
        )
    elif len(layout_problems) == 0 and end < decl.size_bytes:
        result.padding_spans.append(
            PaddingSpan("__pad" + String(len(result.padding_spans)), end, decl.size_bytes - end)
        )
    if decl.align_bytes < natural_align:
        layout_problems.append(
            "C base alignment "
            + String(decl.align_bytes)
            + " is smaller than the natural typed Mojo alignment "
            + String(natural_align)
        )
    result.layout_problems.extend(layout_problems^)
    return result^

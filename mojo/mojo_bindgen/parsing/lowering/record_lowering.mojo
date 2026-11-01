"""Transactional record publication; private mutable fields never escape early."""
from clang.cindex import Cursor, CursorKind, TypeKind
from std.memory import ArcPointer
from ...ir import CType, Struct, Field, FamPattern, CArray, ArrayKind
from ..registry import RecordRegistry, RecordState, decl_id, anonymous, is_record, make_struct_ref
from ..frontend import children, tokens
from ..doc_comments import cursor_doc_comment
from .type_lowering import lower_type, TypeContext


def lower_record(mut registry: RecordRegistry, ref cursor: Cursor) raises -> Struct:
    var key = decl_id(cursor)
    if key in registry.states:
        match registry.states[key]:
            case .completed(v):
                return v.copy()
            case _:
                pass
    var name = registry.naming(cursor)
    var t = cursor.type()
    var record = Struct(
        key.copy(),
        name.copy(),
        name.copy(),
        [],
        max(0, t.size()),
        max(1, t.align()),
        cursor.kind() == CursorKind.UNION_DECL,
        anonymous(cursor.spelling()),
        False,
        doc=cursor_doc_comment(cursor),
    )
    var prior = registry.begin(record)
    try:
        record.fields = lower_fields(registry, cursor, record)
        var nodes = children(cursor)
        for child in nodes:
            if child.kind() == CursorKind.PACKED_ATTR:
                record.is_packed = True
            elif child.kind() == CursorKind.ALIGNED_ATTR:
                record.requested_align_bytes = record.align_bytes
        var spellings = tokens(cursor)
        if "_Alignas" in spellings or "alignas" in spellings:
            record.requested_align_bytes = record.align_bytes
        record.is_complete = True
        registry.publish(record)
    except e:
        registry.abort(key, prior)
        raise e
    return record^


def lower_fields(
    mut registry: RecordRegistry, ref cursor: Cursor, record: Struct
) raises -> List[Field]:
    var nodes = children(cursor)
    var sites = List[Cursor]()
    var parent_type = cursor.type()
    for child in nodes:
        if child.kind() == CursorKind.FIELD_DECL:
            sites.append(child.copy())
        elif is_record(child) and child.is_definition() and anonymous(child.spelling()):
            var explicit = False
            for sibling in nodes:
                if sibling.kind() == CursorKind.FIELD_DECL:
                    var shape = sibling.type().canonical()
                    var definition = shape.declaration()
                    if definition and decl_id(definition.value()) == decl_id(child):
                        explicit = True
            if not explicit:
                sites.append(child.copy())
    var result = List[Field]()
    for i in range(len(sites)):
        var child = sites[i].copy()
        var direct = is_record(child)
        var ft = child.type()
        var name = child.spelling()
        var source_name = name.copy()
        var offset = 0
        var field_cursor = Optional[Cursor](child.copy())
        if direct:
            name = ""
            source_name = ""
            field_cursor = None
            for implicit in parent_type.fields():
                var shape = implicit.type().canonical()
                var definition = shape.declaration()
                if definition and decl_id(definition.value()) == decl_id(child):
                    field_cursor = implicit.copy()
                    break
        if field_cursor:
            offset = field_cursor.value().offset_of_field()
        var bitfield = False
        var width = 0
        if field_cursor:
            bitfield = field_cursor.value().is_bitfield()
            if bitfield:
                width = field_cursor.value().bitfield_width()
        for attached in children(child):
            if is_record(attached) and attached.is_definition():
                _ = lower_record(registry, attached)
        var lowered: CType
        if direct:
            lowered = CType.struct_ref(make_struct_ref(lower_record(registry, child)))
        else:
            lowered = lower_type(registry, ft, TypeContext.FIELD, field_cursor)
        if bitfield and not integer_backing(lowered):
            registry.add_cursor_diag(
                "warning",
                child,
                "bitfield backing type is not an integer after typedef/cv/atomic peeling; field skipped",
            )
            continue
        var fam = Optional[FamPattern]()
        if not record.is_union and field_cursor:
            match lowered:
                case .c_array(v):
                    if v.array_kind == ArrayKind.flexible and not v.size:
                        fam = FamPattern.c99_empty
                    elif v.size and v.size.value() == 0 and v.array_kind == ArrayKind.fixed:
                        fam = FamPattern.gnu_zero
                case _:
                    pass
            if fam and i != len(sites) - 1:
                fam = None
                registry.add_cursor_diag(
                    "warning",
                    child,
                    "non-trailing flexible tail array is not modeled as a flexible array member",
                )
        result.append(
            Field(
                name^,
                source_name^,
                ArcPointer(lowered^),
                max(0, offset) // 8,
                max(0, ft.size()),
                direct or not Bool(child.spelling()),
                bitfield,
                max(0, offset) if bitfield else 0,
                width,
                fam^,
                cursor_doc_comment(child),
            )
        )
    return result^


def integer_backing(t: CType) -> Bool:
    match t:
        case .int_type(_):
            return True
        case .type_ref(v):
            return integer_backing(v.canonical.ptr()[])
        case .qualified_type(v):
            return integer_backing(v.unqualified.ptr()[])
        case .atomic_type(v):
            return integer_backing(v.value_type.ptr()[])
        case _:
            return False

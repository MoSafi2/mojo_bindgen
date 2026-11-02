from std.memory import ArcPointer
from ...ir import *
from ..common import quoted, mojo_align_decorator_ok
from ..facts.context import AnalysisContext
from ..facts.representation import storage_type
from ..facts.record_layout import RecordLayoutFacts
from ..facts.record_storage import RecordStorageKind
from .mapping_support import (
    record_name,
    field_mojo_name,
    field_display_name,
    try_map_type,
    struct_note,
)
from .type_mapping import MapTypePass


@fieldwise_init
struct StructMappingContext(Copyable, Movable):
    var facts: ArcPointer[AnalysisContext]
    var type_mapper: MapTypePass


@fieldwise_init
struct _Member(Copyable, Movable):
    var offset: Int
    var index: Int
    var member: StructMember


def _diagnostics(
    facts: RecordLayoutFacts, notes: List[String], reasons: List[String]
) -> List[MappingNote]:
    var out = List[MappingNote]()
    for p in facts.layout_problems:
        out.append(struct_note(p + "; opaque storage emitted"))
    for p in notes:
        out.append(struct_note(p))
    for p in reasons:
        out.append(struct_note(p))
    return out^


def _opaque(
    decl: Struct, facts: RecordLayoutFacts, notes: List[String], reasons: List[String]
) -> StructDecl:
    if case .builtin_type(_) = storage_type(facts.size_bytes, facts.align_bytes):
        var unsupported = StructDecl(record_name(decl), kind=StructKind.OPAQUE, doc=decl.doc.copy())
        unsupported.diagnostics = _diagnostics(facts, notes, reasons)
        unsupported.diagnostics.append(
            struct_note(
                "record has no representable storage geometry; incomplete placeholder emitted"
            )
        )
        return unsupported^
    var result = StructDecl(
        record_name(decl), kind=StructKind.PLAIN, align=facts.align_bytes, doc=decl.doc.copy()
    )
    if (
        facts.align_bytes
        and facts.align_bytes.value() > 1
        and mojo_align_decorator_ok(facts.align_bytes.value())
    ):
        result.align_decorator = facts.align_bytes
    result.members.append(
        StructMember.opaque_storage_member(OpaqueStorageMember("storage", facts.size_bytes))
    )
    result.diagnostics = _diagnostics(facts, notes, reasons)
    return result^


def map_struct(decl: Struct, context: StructMappingContext) raises -> StructDecl:
    if decl.is_union:
        raise Error("expected non-union Struct declaration, got union " + quoted(decl.decl_id))
    ref storage = context.facts[].record_storage[decl.decl_id]
    ref facts = storage.layout
    if storage.storage_kind == RecordStorageKind.INCOMPLETE:
        return StructDecl(record_name(decl), kind=StructKind.OPAQUE, doc=decl.doc.copy())
    if storage.storage_kind == RecordStorageKind.OPAQUE_STORAGE:
        return _opaque(decl, facts, storage.diagnostic_notes, storage.fallback_reasons)
    var plain = List[StoredMember]()
    var groups = List[BitfieldGroupMember]()
    var reasons = List[String]()
    var notes = List[String]()
    for f in facts.plain_fields:
        var field = decl.fields[f.index].copy()
        var display = field_display_name(field, f.index)
        var mapped = try_map_type(
            context.type_mapper,
            field.type.ptr()[],
            "field `" + display + "`",
            "opaque storage emitted",
        )
        if mapped[1] or not mapped[0]:
            if mapped[1]:
                reasons.append(mapped[1].value().copy())
            continue
        var atomic = False
        match field.type.ptr()[]:
            case .atomic_type(_):
                atomic = True
            case _:
                pass
        if atomic:
            match mapped[0].value().ptr()[]:
                case .parametric_type(v):
                    atomic = v.base != ParametricBase.ATOMIC
                case _:
                    pass
            if atomic:
                reasons.append(
                    "atomic field `"
                    + display
                    + "` has no layout-compatible Atomic[T]; opaque storage emitted"
                )
        plain.append(
            StoredMember(
                f.index,
                field_mojo_name(field, f.index),
                mapped[0].value().copy(),
                f.byte_offset,
                field.doc.copy(),
            )
        )
    for run in facts.bitfield_runs:
        var mapped = try_map_type(
            context.type_mapper,
            CType.int_type(run.unsigned_storage_type.copy()),
            "bitfield storage `" + run.name + "`",
            "opaque storage emitted",
        )
        if mapped[1] or not mapped[0]:
            if mapped[1]:
                reasons.append(mapped[1].value().copy())
            continue
        var fields = List[BitfieldField]()
        for f in run.fields:
            var logical = try_map_type(
                context.type_mapper,
                f.logical_type.ptr()[],
                "bitfield `" + field_display_name(f.field, f.index) + "`",
                "opaque storage emitted",
            )
            if logical[1] or not logical[0]:
                if logical[1]:
                    reasons.append(logical[1].value().copy())
                continue
            fields.append(
                BitfieldField(
                    f.index,
                    field_mojo_name(f.field, f.index),
                    logical[0].value().copy(),
                    f.bit_offset,
                    f.bit_width,
                    f.signed,
                    f.bool_semantics,
                    f.field.doc.copy(),
                )
            )
        groups.append(
            BitfieldGroupMember(
                run.name.copy(),
                mapped[0].value().copy(),
                run.byte_offset,
                run.first_index,
                run.storage_width_bits,
                fields^,
            )
        )
    if len(reasons):
        return _opaque(decl, facts, notes, reasons)
    var result = StructDecl(
        record_name(decl),
        kind=StructKind.PLAIN,
        align=facts.align_bytes,
        flexible_tail=storage.flexible_tail.copy(),
        doc=decl.doc.copy(),
    )
    if (
        facts.align_bytes
        and facts.align_bytes.value()
        > (facts.natural_typed_align_bytes.value() if facts.natural_typed_align_bytes else 1)
        and mojo_align_decorator_ok(facts.align_bytes.value())
    ):
        result.align_decorator = facts.align_bytes
    var members = List[_Member]()
    for f in plain:
        members.append(_Member(f.byte_offset, f.index, StructMember.stored_member(f.copy())))
    if not facts.is_pure_bitfield():
        for i in range(len(facts.padding_spans)):
            var p = facts.padding_spans[i].copy()
            members.append(
                _Member(
                    p.byte_offset,
                    len(decl.fields) + len(groups) + i,
                    StructMember.padding_member(
                        PaddingMember(p.name.copy(), p.size_bytes, p.byte_offset)
                    ),
                )
            )
    for g in groups:
        members.append(
            _Member(g.byte_offset, g.first_index, StructMember.bitfield_group_member(g.copy()))
        )

    def earlier(a: _Member, b: _Member) -> Bool:
        return a.offset < b.offset or (a.offset == b.offset and a.index < b.index)

    sort[stable=True](Span(members), earlier)
    for member in members:
        result.members.append(member.member.copy())
    if facts.is_pure_bitfield():
        result.initializers.append(Initializer())
        var params = List[InitializerParam]()
        for group in groups:
            var fields = group.fields.copy()

            def earlier_field(a: BitfieldField, b: BitfieldField) -> Bool:
                return a.index < b.index

            sort[stable=True](Span(fields), earlier_field)
            for f in fields:
                params.append(InitializerParam(f.name.copy(), f.logical_type.copy()))
        if len(params):
            result.initializers.append(Initializer(params^))
    result.diagnostics = _diagnostics(facts, notes, List[String]())
    return result^

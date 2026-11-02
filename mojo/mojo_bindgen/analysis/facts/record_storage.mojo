from .representation import contains_storage, target_layout, storage_type, RepresentationKind
from .type_layout import peel_layout_wrappers, type_layout
from std.memory import ArcPointer
from ...ir import *
from .record_layout import RecordLayoutFacts, PlainFieldFact, align_up
from ..type_walk import iter_type_nodes, TypeWalkOptions
from ..mojo.type_mapping import MapTypePass
from ..mojo.mapping_support import try_map_type, field_display_name


__enum RecordStorageKind(Equatable, ImplicitlyCopyable, Movable):
    case INCOMPLETE
    case UNION
    case TYPED
    case OPAQUE_STORAGE

    def value(self) -> String:
        match self:
            case .INCOMPLETE:
                return "incomplete"
            case .UNION:
                return "union"
            case .TYPED:
                return "typed"
            case .OPAQUE_STORAGE:
                return "opaque_storage"


struct ByValueEmbeddingDecision(Copyable, Movable):
    var valid: Bool
    var detail: List[String]
    var flexible_tail: Optional[FlexibleTail]

    def __init__(
        out self,
        valid: Bool,
        var detail: List[String] = List[String](),
        var flexible_tail: Optional[FlexibleTail] = {},
    ):
        self.valid = valid
        self.detail = detail^
        self.flexible_tail = flexible_tail^


struct RecordStorageFacts(Copyable, Movable):
    var decl_id: String
    var is_union: Bool
    var is_complete: Bool
    var layout: RecordLayoutFacts
    var storage_kind: RecordStorageKind
    var by_value_embedding: ByValueEmbeddingDecision
    var flexible_tail: Optional[FlexibleTail]
    var diagnostic_notes: List[String]
    var fallback_reasons: List[String]

    var target_layout: Optional[Tuple[Int, Int]]

    def __init__(
        out self,
        var decl_id: String,
        is_union: Bool,
        is_complete: Bool,
        var layout: RecordLayoutFacts,
        storage_kind: RecordStorageKind,
        var by_value_embedding: ByValueEmbeddingDecision,
        var flexible_tail: Optional[FlexibleTail],
        var diagnostic_notes: List[String],
        var fallback_reasons: List[String],
        var target_layout: Optional[Tuple[Int, Int]] = {},
    ):
        self.decl_id = decl_id^
        self.is_union = is_union
        self.is_complete = is_complete
        self.layout = layout^
        self.storage_kind = storage_kind
        self.by_value_embedding = by_value_embedding^
        self.flexible_tail = flexible_tail^
        self.diagnostic_notes = diagnostic_notes^
        self.fallback_reasons = fallback_reasons^
        self.target_layout = target_layout^

    def uses_typed_storage(self) -> Bool:
        return self.storage_kind == RecordStorageKind.TYPED

    def requires_opaque_storage(self) -> Bool:
        return self.storage_kind == RecordStorageKind.OPAQUE_STORAGE

    def layout_known(self) -> Bool:
        return self.layout.is_complete and len(self.layout.layout_problems) == 0


def _failure(message: String) -> ByValueEmbeddingDecision:
    var reasons = List[String]()
    reasons.append(message.copy())
    return ByValueEmbeddingDecision(False, reasons^)


def embedded_struct_refs(t: CType) -> List[StructRef]:
    var out = List[StructRef]()
    for node in iter_type_nodes(
        t,
        TypeWalkOptions(
            descend_pointer=False, descend_function_ptr=False, descend_vector_element=True
        ),
    ):
        match node.ptr()[]:
            case .struct_ref(v):
                if not v.is_union:
                    out.append(v.copy())
            case _:
                pass
    return out^


def direct_embedded_struct_ref(t: CType) -> Optional[StructRef]:
    var core = peel_layout_wrappers(t)
    match core:
        case .struct_ref(v):
            if not v.is_union:
                return v.copy()
        case _:
            pass
    return {}


def _terminal(facts: RecordLayoutFacts, f: PlainFieldFact) -> Bool:
    var end = f.byte_offset + f.size_bytes
    for other in facts.plain_fields:
        if other.index != f.index and other.byte_offset >= end:
            return False
    for run in facts.bitfield_runs:
        if run.byte_offset >= end:
            return False
    return True


def _direct_tail(field: Field, fact: PlainFieldFact, mapped: MojoType) -> ByValueEmbeddingDecision:
    var array = False
    match field.type.ptr()[]:
        case .c_array(_):
            array = True
        case _:
            pass
    if not array or not field.fam_pattern:
        return _failure(
            "flexible tail field did not map from an array type; opaque storage emitted"
        )
    match mapped:
        case .mojo_array(v):
            if v.size == 0:
                return ByValueEmbeddingDecision(
                    True,
                    flexible_tail=FlexibleTail(
                        field.name.copy(),
                        v.element.copy(),
                        field.fam_pattern.value().value(),
                        fact.byte_offset,
                    ),
                )
        case _:
            pass
    return _failure(
        "field `"
        + field_display_name(field, fact.index)
        + "` did not map to Array[..., 0]; opaque storage emitted"
    )


struct RecordStorageAnalyzer(Movable):
    var records_by_decl_id: Dict[String, Struct]
    var record_layouts: Dict[String, RecordLayoutFacts]
    var type_mapper: MapTypePass
    var _record_cache: Dict[String, RecordStorageFacts]
    var _by_value_cache: Dict[String, ByValueEmbeddingDecision]

    def __init__(
        out self,
        var records_by_decl_id: Dict[String, Struct],
        var record_layouts: Dict[String, RecordLayoutFacts],
        var type_mapper: MapTypePass,
    ):
        self.records_by_decl_id = records_by_decl_id^
        self.record_layouts = record_layouts^
        self.type_mapper = type_mapper^
        self._record_cache = Dict[String, RecordStorageFacts]()
        self._by_value_cache = Dict[String, ByValueEmbeddingDecision]()

    def _by_value(
        mut self, key: String, mut active: Dict[String, Bool]
    ) raises -> ByValueEmbeddingDecision:
        if key in self._by_value_cache:
            return self._by_value_cache[key].copy()
        var decision = ByValueEmbeddingDecision(True)
        if key not in self.records_by_decl_id:
            decision = _failure("referenced definition is unavailable")
        else:
            var decl = self.records_by_decl_id[key].copy()
            var facts = self.record_layouts[key].copy()
            if key in active:
                decision = _failure("recursive by-value record")
            elif decl.is_union:
                pass
            elif not decl.is_complete or not facts.is_complete:
                decision = _failure("referenced definition is incomplete")
            elif len(facts.layout_problems):
                decision = _failure(facts.layout_problems[0])
            else:
                active[key] = True
                decision = self._fields(decl, facts, active)
                if decision.valid:
                    var bitfields = self._bitfields(facts)
                    if not bitfields.valid:
                        decision = bitfields^
                _ = active.pop(key)
        self._by_value_cache[key] = decision.copy()
        return decision^

    def _fields(
        mut self, decl: Struct, facts: RecordLayoutFacts, mut active: Dict[String, Bool]
    ) raises -> ByValueEmbeddingDecision:
        var result = ByValueEmbeddingDecision(True)
        for f in facts.plain_fields:
            var field = decl.fields[f.index].copy()
            var mapped = try_map_type(
                self.type_mapper,
                field.type.ptr()[],
                "field `" + field_display_name(field, f.index) + "`",
                "opaque storage emitted",
            )
            if mapped[1] or not mapped[0]:
                return _failure(
                    mapped[1].value() if mapped[1] else String("field could not be mapped")
                )
            var representation = self.type_mapper.run(peel_layout_wrappers(field.type[]))
            if (
                self.type_mapper.representation(peel_layout_wrappers(field.type[])).kind
                != RepresentationKind.VALUE
            ):
                return _failure(
                    "field `"
                    + field_display_name(field, f.index)
                    + "` has no value-compatible Mojo type; opaque storage emitted"
                )
            var source_shape = type_layout(field.type[])
            var target_shape = target_layout(representation, self.type_mapper.queries)
            if source_shape and target_shape and source_shape.value() != target_shape.value():
                return _failure(
                    "field `"
                    + field_display_name(field, f.index)
                    + "` has incompatible target storage geometry; opaque storage emitted"
                )
            if field.fam_pattern:
                var tail = _direct_tail(field, f, mapped[0].value().ptr()[])
                if not tail.valid:
                    return tail^
                result.flexible_tail = tail.flexible_tail.copy()
                continue
            var refs = embedded_struct_refs(field.type.ptr()[])
            var tails = List[ByValueEmbeddingDecision]()
            var tail_refs = List[StructRef]()
            for v in refs:
                var decision = self._by_value(v.decl_id, active)
                if not decision.valid:
                    if self._opaque_embedding(v.decl_id, active):
                        continue
                    var target = v.c_name.copy() if v.c_name.byte_length() else v.name.copy()
                    var suffix = decision.detail[0].copy() if len(decision.detail) else String(
                        "embedded record is not layout-emittable by value"
                    )
                    return _failure(
                        "field `"
                        + field_display_name(field, f.index)
                        + "` embeds struct `"
                        + target
                        + "` by value, but "
                        + suffix
                        + "; opaque storage emitted"
                    )
                if decision.flexible_tail:
                    tails.append(decision^)
                    tail_refs.append(v.copy())
            if len(tails):
                var direct = direct_embedded_struct_ref(field.type.ptr()[])
                if len(tails) > 1 or not direct or tail_refs[0].decl_id != direct.value().decl_id:
                    return _failure(
                        "field `"
                        + field_display_name(field, f.index)
                        + "` embeds a flexible-tail record through a non-direct aggregate type; opaque storage emitted"
                    )
                if not _terminal(facts, f):
                    var target = (
                        tail_refs[0]
                        .c_name.copy() if tail_refs[0]
                        .c_name.byte_length() else tail_refs[0]
                        .name.copy()
                    )
                    return _failure(
                        "field `"
                        + field_display_name(field, f.index)
                        + "` embeds struct `"
                        + target
                        + "` by value, but embedded flexible tail is not terminal in the enclosing record; opaque storage emitted"
                    )
                var tail = tails[0].flexible_tail.value().copy()
                tail.byte_offset += f.byte_offset
                result.flexible_tail = tail^
        return result^

    def _bitfields(self, facts: RecordLayoutFacts) -> ByValueEmbeddingDecision:
        for run in facts.bitfield_runs:
            var mapped = try_map_type(
                self.type_mapper,
                CType.int_type(run.unsigned_storage_type.copy()),
                "bitfield storage `" + run.name + "`",
                "opaque storage emitted",
            )
            if mapped[1]:
                return _failure(mapped[1].value())
            for field in run.fields:
                mapped = try_map_type(
                    self.type_mapper,
                    field.logical_type.ptr()[],
                    "bitfield `" + field_display_name(field.field, field.index) + "`",
                    "opaque storage emitted",
                )
                if mapped[1]:
                    return _failure(mapped[1].value())
        return ByValueEmbeddingDecision(True)

    def _reaches_active(
        self, key: String, active: Dict[String, Bool], mut seen: Dict[String, Bool]
    ) raises -> Bool:
        if key in active:
            return True
        if key in seen or key not in self.records_by_decl_id:
            return False
        seen[key] = True
        for field in self.records_by_decl_id[key].fields:
            for child in embedded_struct_refs(field.type[]):
                if self._reaches_active(child.decl_id, active, seen):
                    return True
        return False

    def _opaque_embedding(mut self, key: String, active: Dict[String, Bool]) raises -> Bool:
        if key not in self.records_by_decl_id:
            return False
        var seen = Dict[String, Bool]()
        if self._reaches_active(key, active, seen):
            return False
        var record = self.records_by_decl_id[key].copy()
        var storage = self.analyze_record(record)
        return storage.storage_kind == RecordStorageKind.OPAQUE_STORAGE and storage.target_layout

    def _mapped_shape(self, t: CType) raises -> Optional[Tuple[Int, Int]]:
        var core = peel_layout_wrappers(t)
        match core:
            case .struct_ref(v):
                if v.decl_id not in self.records_by_decl_id:
                    return {}
                ref decl = self.records_by_decl_id[v.decl_id]
                if not decl.is_complete:
                    return {}
                if decl.size_bytes == 0 and not len(decl.fields) and decl.align_bytes == 1:
                    return (0, 1)
                return target_layout(
                    storage_type(decl.size_bytes, decl.align_bytes), self.type_mapper.queries
                )
            case .enum_ref(v):
                return self._mapped_shape(CType.int_type(v.underlying.copy()))
            case .c_array(v):
                if v.array_kind == ArrayKind.fixed or v.array_kind == ArrayKind.flexible:
                    var child = self._mapped_shape(v.element[])
                    if child:
                        return (
                            child.value()[0] * (v.size.value() if v.size else 0),
                            child.value()[1],
                        )
                return {}
            case _:
                return target_layout(self.type_mapper.run(core), self.type_mapper.queries)

    def _target_geometry(
        self, decl: Struct, facts: RecordLayoutFacts
    ) raises -> Optional[Tuple[Int, Int]]:
        var items = List[Tuple[Int, Int, Int]]()
        for f in facts.plain_fields:
            var shape = self._mapped_shape(decl.fields[f.index].type[])
            if not shape or shape.value()[0] != f.size_bytes:
                return {}
            items.append((f.byte_offset, shape.value()[0], shape.value()[1]))
        for run in facts.bitfield_runs:
            var shape = self._mapped_shape(CType.int_type(run.unsigned_storage_type.copy()))
            if not shape:
                return {}
            items.append((run.byte_offset, shape.value()[0], shape.value()[1]))
        for pad in facts.padding_spans:
            var offset = pad.byte_offset
            var remaining = pad.size_bytes
            while remaining > 0:
                for width in [8, 4, 2, 1]:
                    if remaining >= width and offset % width == 0:
                        items.append(
                            (
                                offset,
                                width,
                                min(width, self.type_mapper.queries.abi.pointer_align_bytes),
                            )
                        )
                        offset += width
                        remaining -= width
                        break
        for i in range(1, len(items)):
            var j = i
            while j > 0 and items[j][0] < items[j - 1][0]:
                var tmp = items[j]
                items[j] = items[j - 1]
                items[j - 1] = tmp
                j -= 1
        var current = 0
        var alignment = 1
        for item in items:
            if item[2] <= 0:
                return {}
            current = align_up(current, item[2])
            if current != item[0]:
                return {}
            current += item[1]
            alignment = max(alignment, item[2])
        if facts.align_bytes:
            alignment = max(alignment, facts.align_bytes.value())
        return (align_up(current, alignment), alignment)

    def analyze_record(mut self, record: Struct) raises -> RecordStorageFacts:
        if record.decl_id in self._record_cache:
            return self._record_cache[record.decl_id].copy()
        var layout = self.record_layouts[record.decl_id].copy()
        var kind = RecordStorageKind.TYPED
        var decision = ByValueEmbeddingDecision(True)
        var reasons = List[String]()
        var complete = record.is_complete
        if record.is_union:
            kind = RecordStorageKind.UNION
        elif not layout.is_complete:
            kind = RecordStorageKind.INCOMPLETE
            complete = False
            decision = _failure("referenced definition is incomplete")
        elif len(layout.layout_problems):
            kind = RecordStorageKind.OPAQUE_STORAGE
            decision = _failure(layout.layout_problems[0])
            reasons = layout.layout_problems.copy()
        else:
            var active = Dict[String, Bool]()
            decision = self._by_value(record.decl_id, active)
            if not decision.valid:
                kind = RecordStorageKind.OPAQUE_STORAGE
                reasons = decision.detail.copy()
        var geometry: Optional[Tuple[Int, Int]] = {}
        if complete:
            if kind == RecordStorageKind.TYPED:
                geometry = self._target_geometry(record, layout)
                if not geometry or geometry.value() != (
                    layout.size_bytes,
                    layout.align_bytes.value(),
                ):
                    kind = RecordStorageKind.OPAQUE_STORAGE
                    reasons.append(
                        "mapped physical fields do not reproduce the source layout; opaque storage emitted"
                    )
            if kind == RecordStorageKind.OPAQUE_STORAGE or kind == RecordStorageKind.UNION:
                geometry = target_layout(
                    storage_type(record.size_bytes, record.align_bytes), self.type_mapper.queries
                )
        var result = RecordStorageFacts(
            record.decl_id.copy(),
            record.is_union,
            complete,
            layout^,
            kind,
            decision.copy(),
            decision.flexible_tail.copy(),
            List[String](),
            reasons^,
            geometry^,
        )
        self._record_cache[record.decl_id] = result.copy()
        return result^


def analyze_record_storage_facts(
    records: Dict[String, Struct], layouts: Dict[String, RecordLayoutFacts], mapper: MapTypePass
) raises -> Dict[String, RecordStorageFacts]:
    var analyzer = RecordStorageAnalyzer(records.copy(), layouts.copy(), mapper.copy())
    var result = Dict[String, RecordStorageFacts]()
    for entry in records.items():
        result[entry.key] = analyzer.analyze_record(entry.value)
    return result^

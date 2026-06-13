"""Central record layout and shape analysis for normalized CIR."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from mojo_bindgen.analysis.facts.record_layout import RecordLayoutFacts
from mojo_bindgen.analysis.mojo.mapping_support import field_display_name, try_map_type
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, collect_type_nodes
from mojo_bindgen.ir import (
    Array,
    FlexibleTail,
    QualifiedType,
    Struct,
    StructRef,
    Type,
    TypeRef,
)


class RecordStorageKind(StrEnum):
    """High-level storage decision for one CIR record."""

    INCOMPLETE = "incomplete"
    UNION = "union"
    TYPED = "typed"
    OPAQUE_STORAGE = "opaque_storage"


@dataclass(frozen=True)
class ByValueRecordShape:
    """Whether a record can be embedded by value in another typed record."""

    valid: bool
    detail: tuple[str, ...] = ()
    flexible_tail: FlexibleTail | None = None


@dataclass(frozen=True)
class RecordAnalysisFacts:
    """Central per-record facts used by struct mapping and later policy passes."""

    decl_id: str
    is_union: bool
    is_complete: bool
    layout: RecordLayoutFacts
    storage_kind: RecordStorageKind
    by_value_shape: ByValueRecordShape
    flexible_tail: FlexibleTail | None = None
    diagnostic_notes: tuple[str, ...] = ()
    fallback_reasons: tuple[str, ...] = ()

    @property
    def typed_storage_candidate(self) -> bool:
        return self.storage_kind == RecordStorageKind.TYPED

    @property
    def opaque_storage_required(self) -> bool:
        return self.storage_kind == RecordStorageKind.OPAQUE_STORAGE

    @property
    def layout_known(self) -> bool:
        return self.layout.is_complete and not self.layout.layout_problems

    @property
    def flexible_tail_field_index(self) -> int | None:
        if self.flexible_tail is None:
            return None
        # Kept for compatibility with the first shape-facts API. Prefer
        # ``flexible_tail`` for new callers.
        return None


def analyze_record_shapes(
    records_by_decl_id: dict[str, Struct],
    record_layouts: dict[str, RecordLayoutFacts],
    *,
    type_mapper: MapTypePass | None = None,
) -> dict[str, RecordAnalysisFacts]:
    """Analyze every CIR record's layout shape and typed-storage eligibility."""

    analyzer = RecordShapeAnalyzer(
        records_by_decl_id=records_by_decl_id,
        record_layouts=record_layouts,
        type_mapper=type_mapper or MapTypePass(),
    )
    return {
        decl_id: analyzer.analyze_record(record) for decl_id, record in records_by_decl_id.items()
    }


def analyze_record_shape(
    record: Struct,
    layout: RecordLayoutFacts,
    *,
    records_by_decl_id: dict[str, Struct] | None = None,
    record_layouts: dict[str, RecordLayoutFacts] | None = None,
    type_mapper: MapTypePass | None = None,
) -> RecordAnalysisFacts:
    """Analyze one CIR record.

    Direct callers can pass only ``record`` and ``layout`` for isolated tests;
    recursive by-value checks use the optional maps when available.
    """

    records = records_by_decl_id or {record.decl_id: record}
    layouts = record_layouts or {record.decl_id: layout}
    return RecordShapeAnalyzer(
        records_by_decl_id=records,
        record_layouts=layouts,
        type_mapper=type_mapper or MapTypePass(),
    ).analyze_record(record)


@dataclass
class RecordShapeAnalyzer:
    """Compute reusable record shape facts for a normalized CIR unit."""

    records_by_decl_id: dict[str, Struct]
    record_layouts: dict[str, RecordLayoutFacts]
    type_mapper: MapTypePass

    def __post_init__(self) -> None:
        self._record_cache: dict[str, RecordAnalysisFacts] = {}
        self._by_value_cache: dict[str, ByValueRecordShape] = {}

    def analyze_record(self, record: Struct) -> RecordAnalysisFacts:
        cached = self._record_cache.get(record.decl_id)
        if cached is not None:
            return cached

        layout = self._layout(record)
        if record.is_union:
            facts = RecordAnalysisFacts(
                decl_id=record.decl_id,
                is_union=True,
                is_complete=record.is_complete,
                layout=layout,
                storage_kind=RecordStorageKind.UNION,
                by_value_shape=ByValueRecordShape(True),
            )
            self._record_cache[record.decl_id] = facts
            return facts

        if not layout.is_complete:
            facts = RecordAnalysisFacts(
                decl_id=record.decl_id,
                is_union=False,
                is_complete=False,
                layout=layout,
                storage_kind=RecordStorageKind.INCOMPLETE,
                by_value_shape=ByValueRecordShape(False, ("referenced definition is incomplete",)),
            )
            self._record_cache[record.decl_id] = facts
            return facts

        if layout.layout_problems:
            facts = RecordAnalysisFacts(
                decl_id=record.decl_id,
                is_union=False,
                is_complete=True,
                layout=layout,
                storage_kind=RecordStorageKind.OPAQUE_STORAGE,
                by_value_shape=ByValueRecordShape(False, (layout.layout_problems[0],)),
                fallback_reasons=layout.layout_problems,
            )
            self._record_cache[record.decl_id] = facts
            return facts

        by_value = self._record_typed_shape_by_value(record.decl_id, active=set())
        storage_kind = (
            RecordStorageKind.TYPED if by_value.valid else RecordStorageKind.OPAQUE_STORAGE
        )
        facts = RecordAnalysisFacts(
            decl_id=record.decl_id,
            is_union=False,
            is_complete=True,
            layout=layout,
            storage_kind=storage_kind,
            by_value_shape=by_value,
            flexible_tail=by_value.flexible_tail,
            fallback_reasons=() if by_value.valid else by_value.detail,
        )
        self._record_cache[record.decl_id] = facts
        return facts

    def _record_typed_shape_by_value(
        self,
        decl_id: str,
        *,
        active: set[str],
    ) -> ByValueRecordShape:
        cached = self._by_value_cache.get(decl_id)
        if cached is not None:
            return cached

        decl, facts, early_shape = self._precheck_by_value_record(decl_id, active)
        if early_shape is not None:
            return self._cache_by_value(decl_id, early_shape)
        assert decl is not None
        assert facts is not None

        active.add(decl_id)
        try:
            field_shape = self._plain_fields_by_value_shape(decl, facts, active=active)
            if not field_shape.valid:
                return self._cache_by_value(decl_id, field_shape)

            bitfield_shape = self._bitfield_runs_by_value_shape(facts)
            if not bitfield_shape.valid:
                return self._cache_by_value(decl_id, bitfield_shape)
        finally:
            active.remove(decl_id)

        return self._cache_by_value(
            decl_id,
            ByValueRecordShape(True, flexible_tail=field_shape.flexible_tail),
        )

    def _precheck_by_value_record(
        self,
        decl_id: str,
        active: set[str],
    ) -> tuple[Struct | None, RecordLayoutFacts | None, ByValueRecordShape | None]:
        decl = self.records_by_decl_id.get(decl_id)
        if decl is None:
            return None, None, ByValueRecordShape(False, ("referenced definition is unavailable",))
        if decl.is_union:
            return None, None, ByValueRecordShape(True)
        if not decl.is_complete:
            return None, None, ByValueRecordShape(False, ("referenced definition is incomplete",))
        if decl_id in active:
            return None, None, ByValueRecordShape(True)

        facts = self._layout(decl)
        if not facts.is_complete:
            return None, None, ByValueRecordShape(False, ("referenced definition is incomplete",))
        if facts.layout_problems:
            return None, None, ByValueRecordShape(False, (facts.layout_problems[0],))
        return decl, facts, None

    def _plain_fields_by_value_shape(
        self,
        decl: Struct,
        facts: RecordLayoutFacts,
        *,
        active: set[str],
    ) -> ByValueRecordShape:
        flexible_tail: FlexibleTail | None = None
        for field_fact in facts.plain_fields:
            field = decl.fields[field_fact.index]
            mapped_type, reason = try_map_type(
                self.type_mapper,
                field.type,
                subject=f"field `{field_display_name(field, field_fact.index)}`",
                failure_suffix="opaque storage emitted",
            )
            if reason is not None or mapped_type is None:
                return ByValueRecordShape(False, ((reason or "field could not be mapped"),))
            if field.fam_pattern is not None:
                tail_shape = _direct_flexible_tail_shape(field, field_fact, mapped_type)
                if not tail_shape.valid:
                    return tail_shape
                flexible_tail = tail_shape.flexible_tail
                continue

            nested_shape = self._nested_record_field_shape(field, field_fact, facts, active=active)
            if not nested_shape.valid:
                return nested_shape
            if nested_shape.flexible_tail is not None:
                flexible_tail = nested_shape.flexible_tail
        return ByValueRecordShape(True, flexible_tail=flexible_tail)

    def _nested_record_field_shape(
        self,
        field,
        field_fact,
        facts: RecordLayoutFacts,
        *,
        active: set[str],
    ) -> ByValueRecordShape:
        refs = _embedded_struct_refs(field.type)
        if not refs:
            return ByValueRecordShape(True)

        nested_tail_shapes: list[tuple[StructRef, ByValueRecordShape]] = []
        for ref in refs:
            shape = self._record_typed_shape_by_value(ref.decl_id, active=active)
            if not shape.valid:
                return _embedded_record_failure(field, field_fact, ref, shape)
            if shape.flexible_tail is not None:
                nested_tail_shapes.append((ref, shape))

        if not nested_tail_shapes:
            return ByValueRecordShape(True)
        return _embedded_flexible_tail_shape(field, field_fact, facts, nested_tail_shapes)

    def _bitfield_runs_by_value_shape(self, facts: RecordLayoutFacts) -> ByValueRecordShape:
        for run_layout in facts.bitfield_runs:
            _, reason = try_map_type(
                self.type_mapper,
                run_layout.unsigned_storage_type,
                subject=f"bitfield storage `{run_layout.name}`",
                failure_suffix="opaque storage emitted",
            )
            if reason is not None:
                return ByValueRecordShape(False, (reason,))

            for field_layout in run_layout.fields:
                _, reason = try_map_type(
                    self.type_mapper,
                    field_layout.logical_type,
                    subject=f"bitfield `{field_display_name(field_layout.field, field_layout.index)}`",
                    failure_suffix="opaque storage emitted",
                )
                if reason is not None:
                    return ByValueRecordShape(False, (reason,))
        return ByValueRecordShape(True)

    def _layout(self, record: Struct) -> RecordLayoutFacts:
        return self.record_layouts[record.decl_id]

    def _cache_by_value(
        self,
        decl_id: str,
        shape: ByValueRecordShape,
    ) -> ByValueRecordShape:
        self._by_value_cache[decl_id] = shape
        return shape


def _map_flexible_tail_metadata(
    field,
    index: int,
    byte_offset: int,
    mapped_type,
) -> tuple[FlexibleTail | None, str | None]:
    if not isinstance(field.type, Array):
        return None, "flexible tail field did not map from an array type; opaque storage emitted"
    if not isinstance(mapped_type, Array) or mapped_type.size != 0:
        return (
            None,
            f"field `{field_display_name(field, index)}` did not map to InlineArray[..., 0]; "
            "opaque storage emitted",
        )
    return (
        FlexibleTail(
            field_name=field.name,
            element_type=mapped_type.element,
            pattern=field.fam_pattern,
            byte_offset=byte_offset,
        ),
        None,
    )


def _direct_flexible_tail_shape(field, field_fact, mapped_type) -> ByValueRecordShape:
    direct_tail, tail_reason = _map_flexible_tail_metadata(
        field,
        field_fact.index,
        field_fact.byte_offset,
        mapped_type,
    )
    if tail_reason is not None or direct_tail is None:
        return ByValueRecordShape(False, ((tail_reason or "flexible tail could not map"),))
    return ByValueRecordShape(True, flexible_tail=direct_tail)


def _embedded_record_failure(
    field,
    field_fact,
    ref: StructRef,
    shape: ByValueRecordShape,
) -> ByValueRecordShape:
    target_name = ref.c_name or ref.name
    suffix = shape.detail[0] if shape.detail else "embedded record is not layout-emittable by value"
    return ByValueRecordShape(
        False,
        (
            f"field `{field_display_name(field, field_fact.index)}` embeds struct "
            f"`{target_name}` by value, but {suffix}; opaque storage emitted",
        ),
    )


def _embedded_flexible_tail_shape(
    field,
    field_fact,
    facts: RecordLayoutFacts,
    nested_tail_shapes: list[tuple[StructRef, ByValueRecordShape]],
) -> ByValueRecordShape:
    direct_ref = _direct_embedded_struct_ref(field.type)
    if len(nested_tail_shapes) > 1 or direct_ref is None:
        return _non_direct_flexible_tail_failure(field, field_fact)

    nested_ref, nested_shape = nested_tail_shapes[0]
    if nested_ref.decl_id != direct_ref.decl_id:
        return _non_direct_flexible_tail_failure(field, field_fact)
    if not _field_is_terminal_in_enclosing_record(facts, field_fact):
        target_name = nested_ref.c_name or nested_ref.name
        return ByValueRecordShape(
            False,
            (
                f"field `{field_display_name(field, field_fact.index)}` embeds struct "
                f"`{target_name}` by value, but embedded flexible tail is not terminal "
                "in the enclosing record; opaque storage emitted",
            ),
        )

    assert nested_shape.flexible_tail is not None
    return ByValueRecordShape(
        True,
        flexible_tail=replace(
            nested_shape.flexible_tail,
            byte_offset=field_fact.byte_offset + nested_shape.flexible_tail.byte_offset,
        ),
    )


def _non_direct_flexible_tail_failure(field, field_fact) -> ByValueRecordShape:
    return ByValueRecordShape(
        False,
        (
            f"field `{field_display_name(field, field_fact.index)}` embeds a flexible-tail "
            "record through a non-direct aggregate type; opaque storage emitted",
        ),
    )


def _direct_embedded_struct_ref(t: Type) -> StructRef | None:
    while True:
        if isinstance(t, QualifiedType):
            t = t.unqualified
            continue
        if isinstance(t, TypeRef):
            t = t.canonical
            continue
        break
    if isinstance(t, StructRef) and not t.is_union:
        return t
    return None


def _field_is_terminal_in_enclosing_record(
    facts: RecordLayoutFacts,
    field_fact,
) -> bool:
    field_end = field_fact.byte_offset + field_fact.size_bytes
    if any(
        other.byte_offset >= field_end
        for other in facts.plain_fields
        if other.index != field_fact.index
    ):
        return False
    if any(run.byte_offset >= field_end for run in facts.bitfield_runs):
        return False
    return True


def _embedded_struct_refs(t: Type) -> tuple[StructRef, ...]:
    return tuple(
        node
        for node in collect_type_nodes(
            t,
            lambda node: isinstance(node, StructRef) and not node.is_union,
            options=TypeWalkOptions(
                descend_pointer=False,
                descend_function_ptr=False,
                descend_vector_element=True,
            ),
        )
        if isinstance(node, StructRef)
    )


# Compatibility aliases for the initial lightweight shape API.
RecordShapeFacts = RecordAnalysisFacts


__all__ = [
    "ByValueRecordShape",
    "RecordAnalysisFacts",
    "RecordShapeFacts",
    "RecordShapeAnalyzer",
    "RecordStorageKind",
    "analyze_record_shape",
    "analyze_record_shapes",
]

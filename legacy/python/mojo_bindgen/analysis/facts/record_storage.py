"""Mojo storage decisions for normalized CIR records.

This module consumes :class:`RecordLayoutFacts` plus whole-unit record/type
context. It decides typed-vs-opaque storage, by-value embeddability, and
flexible-tail propagation. It does not recompute C ABI geometry.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from mojo_bindgen.analysis.facts.record_layout import PlainFieldFact, RecordLayoutFacts
from mojo_bindgen.analysis.facts.representation import (
    RepresentationKind,
    storage_type,
    target_layout,
)
from mojo_bindgen.analysis.facts.type_layout import peel_layout_wrappers, type_layout
from mojo_bindgen.analysis.mojo.mapping_support import field_display_name, try_map_type
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, collect_type_nodes
from mojo_bindgen.ir import (
    CArray,
    CType,
    EnumRef,
    Field,
    FlexibleTail,
    MojoArray,
    MojoType,
    QualifiedType,
    Struct,
    StructRef,
    TypeRef,
)


class RecordStorageKind(StrEnum):
    """High-level storage decision for one CIR record."""

    INCOMPLETE = "incomplete"
    UNION = "union"
    TYPED = "typed"
    OPAQUE_STORAGE = "opaque_storage"


@dataclass(frozen=True)
class ByValueEmbeddingDecision:
    """Whether a record can be embedded by value in another typed record."""

    valid: bool
    detail: tuple[str, ...] = ()
    flexible_tail: FlexibleTail | None = None


@dataclass(frozen=True)
class RecordStorageFacts:
    """Central per-record facts used by struct mapping and later policy passes."""

    decl_id: str
    is_union: bool
    is_complete: bool
    layout: RecordLayoutFacts
    storage_kind: RecordStorageKind
    by_value_embedding: ByValueEmbeddingDecision
    flexible_tail: FlexibleTail | None = None
    diagnostic_notes: tuple[str, ...] = ()
    fallback_reasons: tuple[str, ...] = ()
    target_layout: tuple[int, int] | None = None

    @property
    def uses_typed_storage(self) -> bool:
        return self.storage_kind == RecordStorageKind.TYPED

    @property
    def requires_opaque_storage(self) -> bool:
        return self.storage_kind == RecordStorageKind.OPAQUE_STORAGE

    @property
    def layout_known(self) -> bool:
        return self.layout.is_complete and not self.layout.layout_problems


def analyze_record_storage_facts(
    records_by_decl_id: dict[str, Struct],
    record_layouts: dict[str, RecordLayoutFacts],
    *,
    type_mapper: MapTypePass,
) -> dict[str, RecordStorageFacts]:
    """Analyze every CIR record's Mojo storage eligibility."""

    analyzer = RecordStorageAnalyzer(
        records_by_decl_id=records_by_decl_id,
        record_layouts=record_layouts,
        type_mapper=type_mapper,
    )
    return {
        decl_id: analyzer.analyze_record(record) for decl_id, record in records_by_decl_id.items()
    }


def analyze_record_storage(
    record: Struct,
    layout: RecordLayoutFacts,
    *,
    records_by_decl_id: dict[str, Struct] | None = None,
    record_layouts: dict[str, RecordLayoutFacts] | None = None,
    type_mapper: MapTypePass,
) -> RecordStorageFacts:
    """Analyze one CIR record.

    Callers supply a mapper with fixed target queries;
    recursive by-value checks use the optional maps when available.
    """

    records = records_by_decl_id or {record.decl_id: record}
    layouts = record_layouts or {record.decl_id: layout}
    return RecordStorageAnalyzer(
        records_by_decl_id=records,
        record_layouts=layouts,
        type_mapper=type_mapper,
    ).analyze_record(record)


@dataclass
class RecordStorageAnalyzer:
    """Compute reusable record storage facts for a normalized CIR unit."""

    records_by_decl_id: dict[str, Struct]
    record_layouts: dict[str, RecordLayoutFacts]
    type_mapper: MapTypePass

    def __post_init__(self) -> None:
        self._record_cache: dict[str, RecordStorageFacts] = {}
        self._by_value_cache: dict[str, ByValueEmbeddingDecision] = {}

    def analyze_record(self, record: Struct) -> RecordStorageFacts:
        cached = self._record_cache.get(record.decl_id)
        if cached is not None:
            return cached

        layout = self._layout(record)
        if record.is_union:
            facts = RecordStorageFacts(
                decl_id=record.decl_id,
                is_union=True,
                is_complete=record.is_complete,
                layout=layout,
                storage_kind=RecordStorageKind.UNION,
                by_value_embedding=ByValueEmbeddingDecision(True),
            )
            self._record_cache[record.decl_id] = facts
            return facts

        if not layout.is_complete:
            facts = RecordStorageFacts(
                decl_id=record.decl_id,
                is_union=False,
                is_complete=False,
                layout=layout,
                storage_kind=RecordStorageKind.INCOMPLETE,
                by_value_embedding=ByValueEmbeddingDecision(
                    False, ("referenced definition is incomplete",)
                ),
            )
            self._record_cache[record.decl_id] = facts
            return facts

        if layout.layout_problems:
            facts = RecordStorageFacts(
                decl_id=record.decl_id,
                is_union=False,
                is_complete=True,
                layout=layout,
                storage_kind=RecordStorageKind.OPAQUE_STORAGE,
                by_value_embedding=ByValueEmbeddingDecision(False, (layout.layout_problems[0],)),
                fallback_reasons=layout.layout_problems,
                target_layout=target_layout(
                    storage_type(record.size_bytes, record.align_bytes), self.type_mapper.queries
                ),
            )
            self._record_cache[record.decl_id] = facts
            return facts

        by_value = self._record_typed_storage_by_value(record.decl_id, active=set())
        storage_kind = (
            RecordStorageKind.TYPED if by_value.valid else RecordStorageKind.OPAQUE_STORAGE
        )
        geometry = (
            self._target_geometry(record, layout)
            if storage_kind == RecordStorageKind.TYPED
            else None
        )
        reasons = () if by_value.valid else by_value.detail
        if storage_kind == RecordStorageKind.TYPED and geometry != (
            layout.size_bytes,
            layout.align_bytes,
        ):
            storage_kind = RecordStorageKind.OPAQUE_STORAGE
            reasons = (
                *reasons,
                "mapped physical fields do not reproduce the source layout; opaque storage emitted",
            )
        if storage_kind == RecordStorageKind.OPAQUE_STORAGE:
            geometry = target_layout(
                storage_type(record.size_bytes, record.align_bytes), self.type_mapper.queries
            )
        facts = RecordStorageFacts(
            decl_id=record.decl_id,
            is_union=False,
            is_complete=True,
            layout=layout,
            storage_kind=storage_kind,
            by_value_embedding=by_value,
            flexible_tail=by_value.flexible_tail,
            fallback_reasons=reasons,
            target_layout=geometry,
        )
        self._record_cache[record.decl_id] = facts
        return facts

    def _reaches_active(self, key: str, active: set[str], seen: set[str]) -> bool:
        if key in active:
            return True
        if key in seen or key not in self.records_by_decl_id:
            return False
        seen.add(key)
        return any(
            self._reaches_active(child.decl_id, active, seen)
            for field in self.records_by_decl_id[key].fields
            for child in _embedded_struct_refs(field.type)
        )

    def _opaque_embedding(self, key: str, active: set[str]) -> bool:
        if key not in self.records_by_decl_id or self._reaches_active(key, active, set()):
            return False
        storage = self.analyze_record(self.records_by_decl_id[key])
        return (
            storage.storage_kind == RecordStorageKind.OPAQUE_STORAGE
            and storage.target_layout is not None
        )

    def _mapped_shape(self, t: CType) -> tuple[int, int] | None:
        core = peel_layout_wrappers(t)
        if isinstance(core, StructRef):
            decl = self.records_by_decl_id.get(core.decl_id)
            if decl is None or not decl.is_complete:
                return None
            if decl.size_bytes == 0 and not decl.fields and decl.align_bytes == 1:
                return 0, 1
            return target_layout(
                storage_type(decl.size_bytes, decl.align_bytes), self.type_mapper.queries
            )
        if isinstance(core, EnumRef):
            return self._mapped_shape(core.underlying)
        if isinstance(core, CArray):
            if core.array_kind not in ("fixed", "flexible"):
                return None
            child = self._mapped_shape(core.element)
            return None if child is None else (child[0] * (core.size or 0), child[1])
        return target_layout(self.type_mapper.run(core), self.type_mapper.queries)

    def _target_geometry(self, decl: Struct, facts: RecordLayoutFacts) -> tuple[int, int] | None:
        items: list[tuple[int, int, int]] = []
        for f in facts.plain_fields:
            shape = self._mapped_shape(decl.fields[f.index].type)
            if shape is None or shape[0] != f.size_bytes:
                return None
            items.append((f.byte_offset, *shape))
        for run in facts.bitfield_runs:
            shape = self._mapped_shape(run.unsigned_storage_type)
            if shape is None:
                return None
            items.append((run.byte_offset, *shape))
        for pad in facts.padding_spans:
            offset, remaining = pad.byte_offset, pad.size_bytes
            while remaining > 0:
                width = next(n for n in (8, 4, 2, 1) if remaining >= n and offset % n == 0)
                items.append(
                    (offset, width, min(width, self.type_mapper.queries._abi.pointer_align_bytes))
                )
                offset += width
                remaining -= width
        current, alignment = 0, 1
        for offset, size, align in sorted(items, key=lambda item: item[0]):
            if align <= 0:
                return None
            current = (current + align - 1) // align * align
            if current != offset:
                return None
            current += size
            alignment = max(alignment, align)
        alignment = max(alignment, facts.align_bytes or 1)
        return (current + alignment - 1) // alignment * alignment, alignment

    def _record_typed_storage_by_value(
        self,
        decl_id: str,
        *,
        active: set[str],
    ) -> ByValueEmbeddingDecision:
        cached = self._by_value_cache.get(decl_id)
        if cached is not None:
            return cached

        decl, facts, early_decision = self._precheck_by_value_record(decl_id, active)
        if early_decision is not None:
            return self._cache_by_value(decl_id, early_decision)
        assert decl is not None
        assert facts is not None

        active.add(decl_id)
        try:
            field_decision = self._plain_fields_by_value_embedding(decl, facts, active=active)
            if not field_decision.valid:
                return self._cache_by_value(decl_id, field_decision)

            bitfield_decision = self._bitfield_runs_by_value_embedding(facts)
            if not bitfield_decision.valid:
                return self._cache_by_value(decl_id, bitfield_decision)
        finally:
            active.remove(decl_id)

        return self._cache_by_value(
            decl_id,
            ByValueEmbeddingDecision(True, flexible_tail=field_decision.flexible_tail),
        )

    def _precheck_by_value_record(
        self,
        decl_id: str,
        active: set[str],
    ) -> tuple[Struct | None, RecordLayoutFacts | None, ByValueEmbeddingDecision | None]:
        decl = self.records_by_decl_id.get(decl_id)
        if decl is None:
            return (
                None,
                None,
                ByValueEmbeddingDecision(False, ("referenced definition is unavailable",)),
            )
        if decl.is_union:
            return None, None, ByValueEmbeddingDecision(True)
        if not decl.is_complete:
            return (
                None,
                None,
                ByValueEmbeddingDecision(False, ("referenced definition is incomplete",)),
            )
        if decl_id in active:
            return None, None, ByValueEmbeddingDecision(False, ("recursive by-value record",))

        facts = self._layout(decl)
        if not facts.is_complete:
            return (
                None,
                None,
                ByValueEmbeddingDecision(False, ("referenced definition is incomplete",)),
            )
        if facts.layout_problems:
            return None, None, ByValueEmbeddingDecision(False, (facts.layout_problems[0],))
        return decl, facts, None

    def _plain_fields_by_value_embedding(
        self,
        decl: Struct,
        facts: RecordLayoutFacts,
        *,
        active: set[str],
    ) -> ByValueEmbeddingDecision:
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
                return ByValueEmbeddingDecision(False, ((reason or "field could not be mapped"),))
            representation = self.type_mapper.run(peel_layout_wrappers(field.type))
            if (
                self.type_mapper.representation(peel_layout_wrappers(field.type)).kind
                != RepresentationKind.VALUE
            ):
                return ByValueEmbeddingDecision(
                    False,
                    (
                        f"field `{field_display_name(field, field_fact.index)}` has no value-compatible Mojo type; opaque storage emitted",
                    ),
                )
            source_shape = type_layout(field.type)
            target_shape = target_layout(representation, self.type_mapper.queries)
            if (
                source_shape is not None
                and target_shape is not None
                and source_shape != target_shape
            ):
                return ByValueEmbeddingDecision(
                    False,
                    (
                        f"field `{field_display_name(field, field_fact.index)}` has incompatible target storage geometry; opaque storage emitted",
                    ),
                )
            if field.fam_pattern is not None:
                tail_decision = _direct_flexible_tail_decision(field, field_fact, mapped_type)
                if not tail_decision.valid:
                    return tail_decision
                flexible_tail = tail_decision.flexible_tail
                continue

            nested_decision = self._nested_record_field_decision(
                field,
                field_fact,
                facts,
                active=active,
            )
            if not nested_decision.valid:
                return nested_decision
            if nested_decision.flexible_tail is not None:
                flexible_tail = nested_decision.flexible_tail
        return ByValueEmbeddingDecision(True, flexible_tail=flexible_tail)

    def _nested_record_field_decision(
        self,
        field: Field,
        field_fact: PlainFieldFact,
        facts: RecordLayoutFacts,
        *,
        active: set[str],
    ) -> ByValueEmbeddingDecision:
        refs = _embedded_struct_refs(field.type)
        if not refs:
            return ByValueEmbeddingDecision(True)

        nested_tail_decisions: list[tuple[StructRef, ByValueEmbeddingDecision]] = []
        for ref in refs:
            decision = self._record_typed_storage_by_value(ref.decl_id, active=active)
            if not decision.valid:
                if self._opaque_embedding(ref.decl_id, active):
                    continue
                return _embedded_record_failure(field, field_fact, ref, decision)
            if decision.flexible_tail is not None:
                nested_tail_decisions.append((ref, decision))

        if not nested_tail_decisions:
            return ByValueEmbeddingDecision(True)
        return _embedded_flexible_tail_decision(field, field_fact, facts, nested_tail_decisions)

    def _bitfield_runs_by_value_embedding(
        self, facts: RecordLayoutFacts
    ) -> ByValueEmbeddingDecision:
        for run_layout in facts.bitfield_runs:
            _, reason = try_map_type(
                self.type_mapper,
                run_layout.unsigned_storage_type,
                subject=f"bitfield storage `{run_layout.name}`",
                failure_suffix="opaque storage emitted",
            )
            if reason is not None:
                return ByValueEmbeddingDecision(False, (reason,))

            for field_layout in run_layout.fields:
                _, reason = try_map_type(
                    self.type_mapper,
                    field_layout.logical_type,
                    subject=f"bitfield `{field_display_name(field_layout.field, field_layout.index)}`",
                    failure_suffix="opaque storage emitted",
                )
                if reason is not None:
                    return ByValueEmbeddingDecision(False, (reason,))
        return ByValueEmbeddingDecision(True)

    def _layout(self, record: Struct) -> RecordLayoutFacts:
        return self.record_layouts[record.decl_id]

    def _cache_by_value(
        self,
        decl_id: str,
        decision: ByValueEmbeddingDecision,
    ) -> ByValueEmbeddingDecision:
        self._by_value_cache[decl_id] = decision
        return decision


def _map_flexible_tail_metadata(
    field: Field,
    index: int,
    byte_offset: int,
    mapped_type: MojoType,
) -> tuple[FlexibleTail | None, str | None]:
    if not isinstance(field.type, CArray) or field.fam_pattern is None:
        return None, "flexible tail field did not map from an array type; opaque storage emitted"
    if not isinstance(mapped_type, MojoArray) or mapped_type.size != 0:
        return (
            None,
            f"field `{field_display_name(field, index)}` did not map to Array[..., 0]; "
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


def _direct_flexible_tail_decision(
    field: Field, field_fact: PlainFieldFact, mapped_type: MojoType
) -> ByValueEmbeddingDecision:
    direct_tail, tail_reason = _map_flexible_tail_metadata(
        field,
        field_fact.index,
        field_fact.byte_offset,
        mapped_type,
    )
    if tail_reason is not None or direct_tail is None:
        return ByValueEmbeddingDecision(False, ((tail_reason or "flexible tail could not map"),))
    return ByValueEmbeddingDecision(True, flexible_tail=direct_tail)


def _embedded_record_failure(
    field: Field,
    field_fact: PlainFieldFact,
    ref: StructRef,
    decision: ByValueEmbeddingDecision,
) -> ByValueEmbeddingDecision:
    target_name = ref.c_name or ref.name
    suffix = (
        decision.detail[0]
        if decision.detail
        else "embedded record is not layout-emittable by value"
    )
    return ByValueEmbeddingDecision(
        False,
        (
            f"field `{field_display_name(field, field_fact.index)}` embeds struct "
            f"`{target_name}` by value, but {suffix}; opaque storage emitted",
        ),
    )


def _embedded_flexible_tail_decision(
    field: Field,
    field_fact: PlainFieldFact,
    facts: RecordLayoutFacts,
    nested_tail_decisions: list[tuple[StructRef, ByValueEmbeddingDecision]],
) -> ByValueEmbeddingDecision:
    direct_ref = _direct_embedded_struct_ref(field.type)
    if len(nested_tail_decisions) > 1 or direct_ref is None:
        return _non_direct_flexible_tail_failure(field, field_fact)

    nested_ref, nested_decision = nested_tail_decisions[0]
    if nested_ref.decl_id != direct_ref.decl_id:
        return _non_direct_flexible_tail_failure(field, field_fact)
    if not _field_is_terminal_in_enclosing_record(facts, field_fact):
        target_name = nested_ref.c_name or nested_ref.name
        return ByValueEmbeddingDecision(
            False,
            (
                f"field `{field_display_name(field, field_fact.index)}` embeds struct "
                f"`{target_name}` by value, but embedded flexible tail is not terminal "
                "in the enclosing record; opaque storage emitted",
            ),
        )

    assert nested_decision.flexible_tail is not None
    return ByValueEmbeddingDecision(
        True,
        flexible_tail=replace(
            nested_decision.flexible_tail,
            byte_offset=field_fact.byte_offset + nested_decision.flexible_tail.byte_offset,
        ),
    )


def _non_direct_flexible_tail_failure(
    field: Field, field_fact: PlainFieldFact
) -> ByValueEmbeddingDecision:
    return ByValueEmbeddingDecision(
        False,
        (
            f"field `{field_display_name(field, field_fact.index)}` embeds a flexible-tail "
            "record through a non-direct aggregate type; opaque storage emitted",
        ),
    )


def _direct_embedded_struct_ref(t: CType) -> StructRef | None:
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
    field_fact: PlainFieldFact,
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


def _embedded_struct_refs(t: CType) -> tuple[StructRef, ...]:
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


__all__ = [
    "ByValueEmbeddingDecision",
    "RecordStorageFacts",
    "RecordStorageAnalyzer",
    "RecordStorageKind",
    "analyze_record_storage",
    "analyze_record_storage_facts",
]

"""Pure record layout and representability analysis over CIR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.codegen.mojo_mapper import map_atomic_type
from mojo_bindgen.ir import AtomicType, Field, Struct, TargetABI, Unit
from mojo_bindgen.new_analysis.bitfield_layout import (
    BitfieldRunLayout,
    analyze_bitfield_layout,
)
from mojo_bindgen.new_analysis.lowering_support import field_display_name
from mojo_bindgen.new_analysis.type_layout import type_layout
from mojo_bindgen.new_analysis.type_walk import TypeWalkOptions, any_type_node


def struct_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map struct ``decl_id`` to :class:`Struct`, including incomplete non-unions."""
    out: dict[str, Struct] = {}
    for decl in unit.decls:
        if isinstance(decl, Struct) and not decl.is_union:
            out[decl.decl_id] = decl
    return out


_EMBEDDED_ATOMIC_WALK = TypeWalkOptions(
    peel_typeref=True,
    peel_qualified=True,
    peel_atomic=False,
    descend_pointer=False,
    descend_array=True,
    descend_function_ptr=False,
    descend_vector_element=False,
)


def field_contains_representable_atomic_storage(field: Field) -> bool:
    return any_type_node(
        field.type,
        lambda node: isinstance(node, AtomicType) and map_atomic_type(node) is not None,
        options=_EMBEDDED_ATOMIC_WALK,
    )


@dataclass(frozen=True)
class PlainFieldFact:
    index: int
    field: Field
    byte_offset: int
    size_bytes: int
    align_bytes: int


@dataclass(frozen=True)
class PaddingSpan:
    name: str
    byte_offset: int
    size_bytes: int


@dataclass(frozen=True)
class RecordLayoutFacts:
    decl: Struct
    is_complete: bool = False
    size_bytes: int = 0
    align_bytes: int | None = None
    is_packed: bool = False
    requested_align_bytes: int | None = None
    natural_typed_align_bytes: int | None = None
    plain_fields: tuple[PlainFieldFact, ...] = ()
    bitfield_runs: tuple[BitfieldRunLayout, ...] = ()
    padding_spans: tuple[PaddingSpan, ...] = ()
    layout_problems: tuple[str, ...] = ()
    has_representable_atomic_storage: bool = False

    @property
    def has_bitfields(self) -> bool:
        return bool(self.bitfield_runs) or any(field.is_bitfield for field in self.decl.fields)

    @property
    def is_pure_bitfield(self) -> bool:
        return bool(self.bitfield_runs) and not self.plain_fields


@dataclass(frozen=True)
class _LayoutItem:
    kind: Literal["field", "bitfield_run"]
    index: int
    byte_offset: int
    size_bytes: int
    align_bytes: int


class AnalyzeRecordLayoutPass:
    """Analyze one CIR struct into pure layout and representability facts."""

    def run(
        self,
        decl: Struct,
        *,
        target_abi: TargetABI,
        record_map: dict[str, Struct] | None = None,
        struct_map: dict[str, Struct] | None = None,
    ) -> RecordLayoutFacts:
        resolved_record_map = _resolve_record_map(record_map=record_map, struct_map=struct_map)
        has_atomic_storage = any(
            field_contains_representable_atomic_storage(field) for field in decl.fields
        )

        # Bail out early if the struct is not complete
        if not decl.is_complete:
            return RecordLayoutFacts(
                decl=decl,
                size_bytes=decl.size_bytes,
                is_packed=decl.is_packed,
                requested_align_bytes=decl.requested_align_bytes,
                has_representable_atomic_storage=has_atomic_storage,
            )

        # Analyze plain fields
        plain_fields, plain_items, plain_problems = self._analyze_plain_fields(
            decl=decl,
            record_map=resolved_record_map,
            target_abi=target_abi,
        )

        # Analyze bitfields
        bitfield_runs, bitfield_problems = analyze_bitfield_layout(decl)
        items = self._sort_layout_items(plain_items, bitfield_runs)

        # Synthesize padding and validate layout
        natural_typed_align = max((item.align_bytes for item in items), default=1)
        padding_spans, layout_problems = self._synthesize_padding_and_validate_layout(
            decl=decl,
            items=items,
            natural_typed_align=natural_typed_align,
        )

        return RecordLayoutFacts(
            decl=decl,
            is_complete=True,
            size_bytes=decl.size_bytes,
            align_bytes=decl.align_bytes,
            is_packed=decl.is_packed,
            requested_align_bytes=decl.requested_align_bytes,
            natural_typed_align_bytes=natural_typed_align,
            plain_fields=tuple(plain_fields),
            bitfield_runs=bitfield_runs,
            padding_spans=tuple(padding_spans),
            layout_problems=tuple([*plain_problems, *bitfield_problems, *layout_problems]),
            has_representable_atomic_storage=has_atomic_storage,
        )

    def _analyze_plain_fields(
        self,
        *,
        decl: Struct,
        record_map: dict[str, Struct],
        target_abi: TargetABI,
    ) -> tuple[list[PlainFieldFact], list[_LayoutItem], list[str]]:
        facts: list[PlainFieldFact] = []
        items: list[_LayoutItem] = []
        problems: list[str] = []

        for index, field in enumerate(decl.fields):
            if field.is_bitfield:
                continue

            field_name = field_display_name(field, index)
            layout = type_layout(field.type, record_map=record_map, target_abi=target_abi)
            if layout is None:
                problems.append(f"field `{field_name}` has unsupported layout metadata")
                continue

            size_bytes, align_bytes = layout
            facts.append(
                PlainFieldFact(
                    index=index,
                    field=field,
                    byte_offset=field.byte_offset,
                    size_bytes=size_bytes,
                    align_bytes=align_bytes,
                )
            )
            items.append(
                _LayoutItem(
                    kind="field",
                    index=index,
                    byte_offset=field.byte_offset,
                    size_bytes=size_bytes,
                    align_bytes=align_bytes,
                )
            )

        return facts, items, problems

    def _sort_layout_items(
        self,
        plain_items: list[_LayoutItem],
        bitfield_runs: tuple[BitfieldRunLayout, ...],
    ) -> list[_LayoutItem]:
        bitfield_items = [
            _LayoutItem(
                kind="bitfield_run",
                index=run.first_index,
                byte_offset=run.byte_offset,
                size_bytes=run.size_bytes,
                align_bytes=run.align_bytes,
            )
            for run in bitfield_runs
        ]

        return sorted(
            [*plain_items, *bitfield_items],
            key=lambda item: (item.byte_offset, item.index),
        )

    def _synthesize_padding_and_validate_layout(
        self,
        *,
        decl: Struct,
        items: list[_LayoutItem],
        natural_typed_align: int,
    ) -> tuple[list[PaddingSpan], list[str]]:
        padding: list[PaddingSpan] = []
        problems: list[str] = []
        current_offset = 0

        for item in items:
            natural_offset = self._align_up(current_offset, item.align_bytes)
            if item.byte_offset < natural_offset:
                problems.append(
                    f"member at byte offset {item.byte_offset} is before the natural typed offset {natural_offset}"
                )
                continue
            if item.align_bytes > 1 and item.byte_offset % item.align_bytes != 0:
                problems.append(
                    f"member at byte offset {item.byte_offset} is not representable with typed alignment {item.align_bytes}"
                )
                continue
            if item.byte_offset > natural_offset:
                padding.append(
                    PaddingSpan(
                        name=f"__pad{len(padding)}",
                        byte_offset=natural_offset,
                        size_bytes=item.byte_offset - natural_offset,
                    )
                )
            current_offset = item.byte_offset + item.size_bytes

        if decl.align_bytes < natural_typed_align:
            problems.append(
                f"C base alignment {decl.align_bytes} is smaller than the natural typed Mojo alignment {natural_typed_align}"
            )
        if current_offset > decl.size_bytes:
            problems.append(
                f"typed members consume {current_offset} bytes, exceeding C size {decl.size_bytes}"
            )
        if not problems and current_offset < decl.size_bytes:
            padding.append(
                PaddingSpan(
                    name=f"__pad{len(padding)}",
                    byte_offset=current_offset,
                    size_bytes=decl.size_bytes - current_offset,
                )
            )
        return padding, problems

    @staticmethod
    def _align_up(offset: int, align: int) -> int:
        if align <= 1:
            return offset
        rem = offset % align
        if rem == 0:
            return offset
        return offset + (align - rem)


def _resolve_record_map(
    *,
    record_map: dict[str, Struct] | None,
    struct_map: dict[str, Struct] | None,
) -> dict[str, Struct]:
    if record_map is not None:
        return record_map
    if struct_map is not None:
        return struct_map
    raise TypeError("AnalyzeRecordLayoutPass.run() requires `record_map`")

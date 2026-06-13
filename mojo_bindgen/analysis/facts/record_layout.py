"""Pure record layout and representability analysis over CIR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.facts.bitfield_layout import BitfieldRunLayout, analyze_bitfield_layout
from mojo_bindgen.analysis.facts.indexes import struct_by_decl_id
from mojo_bindgen.analysis.facts.type_layout import type_align
from mojo_bindgen.analysis.mojo.lowering_support import field_display_name
from mojo_bindgen.ir import Array, Struct, StructRef, TargetABI


@dataclass(frozen=True)
class PlainFieldFact:
    index: int
    byte_offset: int
    size_bytes: int
    align_bytes: int


@dataclass(frozen=True)
class PaddingSpan:
    name: str
    byte_offset: int
    size_bytes: int


@dataclass(frozen=True)
class _LayoutItem:
    index: int
    byte_offset: int
    size_bytes: int
    align_bytes: int


@dataclass(frozen=True)
class RecordLayoutFacts:
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

    @property
    def is_pure_bitfield(self) -> bool:
        return bool(self.bitfield_runs) and not self.plain_fields


def analyze_record_layout(
    decl: Struct,
    *,
    target_abi: TargetABI,
    record_map: dict[str, Struct],
) -> RecordLayoutFacts:
    # Kept in the public signature for callers that pass whole-unit ABI/index
    # context. The current layout facts are fully represented on each record.
    del target_abi, record_map

    if not decl.is_complete:
        return RecordLayoutFacts(
            size_bytes=decl.size_bytes,
            is_packed=decl.is_packed,
            requested_align_bytes=decl.requested_align_bytes,
        )

    plain_fields, plain_problems = _analyze_plain_fields(decl)
    bitfield_runs, bitfield_problems = analyze_bitfield_layout(decl)
    natural_typed_align = max(
        (
            *[field.align_bytes for field in plain_fields],
            *[run.align_bytes for run in bitfield_runs],
        ),
        default=1,
    )
    padding_spans, layout_problems = _synthesize_padding_and_validate_layout(
        decl,
        plain_fields,
        bitfield_runs,
    )
    if decl.align_bytes < natural_typed_align:
        layout_problems.append(
            "C base alignment "
            f"{decl.align_bytes} is smaller than the natural typed Mojo alignment "
            f"{natural_typed_align}"
        )

    return RecordLayoutFacts(
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
    )


def _analyze_plain_fields(decl: Struct) -> tuple[list[PlainFieldFact], list[str]]:
    facts: list[PlainFieldFact] = []
    problems: list[str] = []

    for index, field in enumerate(decl.fields):
        if field.is_bitfield:
            continue

        field_name = field_display_name(field, index)
        align_bytes = type_align(field.type)
        if align_bytes is None or (
            field.size_bytes <= 0
            and not (isinstance(field.type, Array) or isinstance(field.type, StructRef))
        ):
            problems.append(f"field `{field_name}` has unsupported layout metadata")
            continue

        facts.append(
            PlainFieldFact(
                index=index,
                byte_offset=field.byte_offset,
                size_bytes=field.size_bytes,
                align_bytes=align_bytes,
            )
        )
    return facts, problems


def _synthesize_padding_and_validate_layout(
    decl: Struct,
    plain_fields: list[PlainFieldFact],
    bitfield_runs: tuple[BitfieldRunLayout, ...],
) -> tuple[list[PaddingSpan], list[str]]:
    padding: list[PaddingSpan] = []
    problems: list[str] = []
    current_offset = 0

    for item in _layout_items(plain_fields, bitfield_runs):
        current_offset = _validate_layout_item(
            item,
            current_offset=current_offset,
            padding=padding,
            problems=problems,
        )

    _synthesize_trailing_padding(
        decl,
        current_offset=current_offset,
        padding=padding,
        problems=problems,
    )
    return padding, problems


def _layout_items(
    plain_fields: list[PlainFieldFact],
    bitfield_runs: tuple[BitfieldRunLayout, ...],
) -> tuple[_LayoutItem, ...]:
    items = [
        *(
            _LayoutItem(field.index, field.byte_offset, field.size_bytes, field.align_bytes)
            for field in plain_fields
        ),
        *(
            _LayoutItem(run.first_index, run.byte_offset, run.size_bytes, run.align_bytes)
            for run in bitfield_runs
        ),
    ]
    return tuple(sorted(items, key=lambda item: (item.byte_offset, item.index)))


def _validate_layout_item(
    item: _LayoutItem,
    *,
    current_offset: int,
    padding: list[PaddingSpan],
    problems: list[str],
) -> int:
    natural_offset = _align_up(current_offset, item.align_bytes)
    if item.byte_offset < natural_offset:
        problems.append(
            f"member at byte offset {item.byte_offset} is before the natural typed offset {natural_offset}"
        )
        return current_offset
    if item.align_bytes > 1 and item.byte_offset % item.align_bytes != 0:
        problems.append(
            f"member at byte offset {item.byte_offset} is not representable with typed alignment {item.align_bytes}"
        )
        return current_offset
    if item.byte_offset > natural_offset:
        padding.append(
            PaddingSpan(
                name=f"__pad{len(padding)}",
                byte_offset=natural_offset,
                size_bytes=item.byte_offset - natural_offset,
            )
        )
    return item.byte_offset + item.size_bytes


def _synthesize_trailing_padding(
    decl: Struct,
    *,
    current_offset: int,
    padding: list[PaddingSpan],
    problems: list[str],
) -> None:
    implicit_end = _align_up(current_offset, decl.align_bytes)
    if implicit_end > decl.size_bytes:
        problems.append(
            f"typed members consume {implicit_end} bytes after struct alignment, exceeding C size {decl.size_bytes}"
        )
        return
    if not problems and implicit_end < decl.size_bytes:
        padding.append(
            PaddingSpan(
                name=f"__pad{len(padding)}",
                byte_offset=implicit_end,
                size_bytes=decl.size_bytes - implicit_end,
            )
        )


def _align_up(offset: int, align: int) -> int:
    if align <= 1:
        return offset
    rem = offset % align
    if rem == 0:
        return offset
    return offset + (align - rem)


__all__ = [
    "PaddingSpan",
    "PlainFieldFact",
    "RecordLayoutFacts",
    "analyze_record_layout",
    "struct_by_decl_id",
]

"""Pure record layout and representability analysis over CIR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.bitfield_layout import BitfieldRunLayout, analyze_bitfield_layout
from mojo_bindgen.analysis.lowering_support import field_display_name
from mojo_bindgen.analysis.type_layout import type_align
from mojo_bindgen.ir import Struct, TargetABI, Unit


def struct_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map struct ``decl_id`` to :class:`Struct`, including incomplete non-unions."""
    out: dict[str, Struct] = {}
    for decl in unit.decls:
        if isinstance(decl, Struct) and not decl.is_union:
            out[decl.decl_id] = decl
    return out


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
        if align_bytes is None or field.size_bytes <= 0:
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

    layout_items = sorted(
        [
            *(
                (field.index, field.byte_offset, field.size_bytes, field.align_bytes)
                for field in plain_fields
            ),
            *(
                (run.first_index, run.byte_offset, run.size_bytes, run.align_bytes)
                for run in bitfield_runs
            ),
        ],
        key=lambda item: (item[1], item[0]),
    )

    for _, byte_offset, size_bytes, align_bytes in layout_items:
        natural_offset = _align_up(current_offset, align_bytes)
        if byte_offset < natural_offset:
            problems.append(
                f"member at byte offset {byte_offset} is before the natural typed offset {natural_offset}"
            )
            continue
        if align_bytes > 1 and byte_offset % align_bytes != 0:
            problems.append(
                f"member at byte offset {byte_offset} is not representable with typed alignment {align_bytes}"
            )
            continue
        if byte_offset > natural_offset:
            padding.append(
                PaddingSpan(
                    name=f"__pad{len(padding)}",
                    byte_offset=natural_offset,
                    size_bytes=byte_offset - natural_offset,
                )
            )
        current_offset = byte_offset + size_bytes

    implicit_end = _align_up(current_offset, decl.align_bytes)
    if implicit_end > decl.size_bytes:
        problems.append(
            f"typed members consume {implicit_end} bytes after struct alignment, exceeding C size {decl.size_bytes}"
        )
    if not problems and implicit_end < decl.size_bytes:
        padding.append(
            PaddingSpan(
                name=f"__pad{len(padding)}",
                byte_offset=implicit_end,
                size_bytes=decl.size_bytes - implicit_end,
            )
        )
    return padding, problems


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

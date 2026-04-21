"""Struct-specific Mojo analysis."""

from __future__ import annotations

from mojo_bindgen.analysis.common import (
    _POINTER_ALIGN_BYTES,
    _POINTER_SIZE_BYTES,
    field_mojo_name,
    mojo_align_decorator_ok,
    scalar_comment_name,
)
from mojo_bindgen.analysis.layout import (
    bitfield_field_is_bool,
    bitfield_field_is_signed,
    bitfield_storage_width_bits,
    bitfield_unsigned_storage_type,
    struct_has_representable_atomic_storage,
)
from mojo_bindgen.analysis.model import (
    AnalyzedBitfieldLayout,
    AnalyzedBitfieldMember,
    AnalyzedBitfieldStorage,
    AnalyzedField,
    AnalyzedOpaqueStorage,
    AnalyzedPaddingField,
    AnalyzedStruct,
    AnalyzedStructInitializer,
    AnalyzedStructInitParam,
    StructInitKind,
    StructRepresentationMode,
)
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.mojo_mapper import TypeMapper, mojo_ident, peel_wrappers
from mojo_bindgen.ir import (
    Array,
    AtomicType,
    ComplexType,
    EnumRef,
    Field,
    FloatType,
    FunctionPtr,
    IntType,
    OpaqueRecordRef,
    Pointer,
    QualifiedType,
    Struct,
    StructRef,
    Type,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)


class AnalyzeStructLoweringPass:
    """Analyze struct lowering into render-ready facts."""

    def run(
        self,
        decl: Struct,
        *,
        struct_map: dict[str, Struct],
        register_passable: bool,
        field_callback_aliases: dict[tuple[str, int], str] | None,
        options: MojoEmitOptions,
        type_mapper: TypeMapper,
    ) -> AnalyzedStruct:
        header_comment_lines: tuple[str, ...] = ()
        decorator_lines: list[str] = []
        align_decorator_value: int | None = None
        align_stride_warning = False
        align_omit_comment: str | None = None
        if decl.is_complete and options.warn_abi:
            header_comment_lines = (
                f"# struct {decl.c_name} - size={decl.size_bytes} align={decl.align_bytes} (verify packed/aligned ABI)",
            )

        all_fields = tuple(
            self._analyze_field(
                decl_id=decl.decl_id,
                field=field,
                index=index,
                field_callback_aliases=field_callback_aliases,
                options=options,
                type_mapper=type_mapper,
            )
            for index, field in enumerate(decl.fields)
        )
        bitfield_layout = self._analyze_bitfield_layout(
            all_fields, options=options, type_mapper=type_mapper
        )
        fields = tuple(
            analyzed_field for analyzed_field in all_fields if not analyzed_field.field.is_bitfield
        )
        representation_mode, padding_fields, opaque_storage, layout_notes = (
            self._analyze_record_representation(
                decl,
                fields=fields,
                struct_map=struct_map,
            )
        )
        decorator_lines.extend(layout_notes)
        align_decorator_value, align_omit_comment, align_stride_warning = (
            self._analyze_record_alignment(
                decl,
                representation_mode=representation_mode,
                struct_map=struct_map,
                options=options,
            )
        )
        if align_decorator_value is not None:
            decorator_lines.insert(0, f"@align({align_decorator_value})")
        if align_omit_comment is not None:
            decorator_lines.append(align_omit_comment)
        init_kind, synthesized_initializers = self._analyze_struct_initializers(
            fields,
            bitfield_layout,
            type_mapper,
        )
        has_atomic_storage = struct_has_representable_atomic_storage(decl)
        if has_atomic_storage:
            trait_names = ()
        else:
            traits = ["Copyable", "Movable"]
            if register_passable and representation_mode == "fieldwise_exact":
                traits.append("RegisterPassable")
            trait_names = tuple(traits)
        return AnalyzedStruct(
            decl=decl,
            mojo_name=mojo_ident(decl.name.strip() or decl.c_name.strip()),
            register_passable=register_passable,
            representation_mode=representation_mode,
            align_decorator=align_decorator_value,
            align_stride_warning=align_stride_warning,
            align_omit_comment=align_omit_comment,
            header_comment_lines=header_comment_lines,
            decorator_lines=tuple(decorator_lines),
            trait_names=trait_names,
            emit_fieldwise_init=(
                representation_mode != "opaque_storage_exact"
                and init_kind == "fieldwise"
                and not has_atomic_storage
                and decl.is_complete
            ),
            fields=fields,
            padding_fields=padding_fields,
            opaque_storage=opaque_storage,
            bitfield_layout=bitfield_layout,
            init_kind=init_kind,
            synthesized_initializers=synthesized_initializers,
        )

    def _analyze_record_representation(
        self,
        decl: Struct,
        *,
        fields: tuple[AnalyzedField, ...],
        struct_map: dict[str, Struct],
    ) -> tuple[
        StructRepresentationMode,
        tuple[AnalyzedPaddingField, ...],
        AnalyzedOpaqueStorage | None,
        tuple[str, ...],
    ]:
        if not decl.is_complete:
            return "fieldwise_exact", (), None, ()
        if any(field.is_bitfield for field in decl.fields):
            return "fieldwise_exact", (), None, ()

        padding_fields: list[AnalyzedPaddingField] = []
        current_offset = 0
        used_padding = False
        natural_struct_align = 1
        opaque_reasons: list[str] = []

        for analyzed_field in fields:
            field_size_align = self._type_layout(analyzed_field.field.type, struct_map, set())
            if field_size_align is None:
                opaque_reasons.append(
                    f"field `{analyzed_field.field.source_name or analyzed_field.field.name or analyzed_field.mojo_name}` has unsupported layout metadata"
                )
                continue
            field_size, field_align = field_size_align
            natural_struct_align = max(natural_struct_align, field_align)
            c_offset = analyzed_field.field.byte_offset
            natural_offset = self._align_up(current_offset, field_align)
            if c_offset < natural_offset:
                opaque_reasons.append(
                    f"field `{analyzed_field.field.source_name or analyzed_field.field.name or analyzed_field.mojo_name}` is at C offset {c_offset}, before the typed Mojo offset {natural_offset}"
                )
                continue
            if c_offset % field_align != 0:
                opaque_reasons.append(
                    f"field `{analyzed_field.field.source_name or analyzed_field.field.name or analyzed_field.mojo_name}` is at C offset {c_offset}, which is not representable for typed alignment {field_align}"
                )
                continue
            explicit_padding_start = natural_offset
            explicit_padding_bytes = c_offset - natural_offset
            if explicit_padding_bytes > 0:
                used_padding = True
                padding_fields.append(
                    AnalyzedPaddingField(
                        name=f"__pad{len(padding_fields)}",
                        surface_type_text=f"InlineArray[UInt8, {explicit_padding_bytes}]",
                        byte_offset=explicit_padding_start,
                        byte_count=explicit_padding_bytes,
                        comment_lines=(
                            f"# synthesized padding: bytes {explicit_padding_start}..{c_offset - 1}",
                        ),
                    )
                )
            current_offset = c_offset + field_size

        if opaque_reasons:
            return (
                "opaque_storage_exact",
                (),
                self._opaque_storage_for_decl(decl, opaque_reasons),
                (),
            )

        if decl.align_bytes < natural_struct_align:
            return (
                "opaque_storage_exact",
                (),
                self._opaque_storage_for_decl(
                    decl,
                    (
                        f"C base alignment {decl.align_bytes} is smaller than the natural typed Mojo alignment {natural_struct_align}",
                    ),
                ),
                (),
            )

        if current_offset > decl.size_bytes:
            return (
                "opaque_storage_exact",
                (),
                self._opaque_storage_for_decl(
                    decl,
                    (
                        f"typed Mojo fields consume {current_offset} bytes, exceeding C size {decl.size_bytes}",
                    ),
                ),
                (),
            )

        if current_offset < decl.size_bytes:
            used_padding = True
            padding_fields.append(
                AnalyzedPaddingField(
                    name=f"__pad{len(padding_fields)}",
                    surface_type_text=f"InlineArray[UInt8, {decl.size_bytes - current_offset}]",
                    byte_offset=current_offset,
                    byte_count=decl.size_bytes - current_offset,
                    comment_lines=(
                        f"# synthesized trailing padding: bytes {current_offset}..{decl.size_bytes - 1}",
                    ),
                )
            )

        if used_padding:
            return "fieldwise_padded_exact", tuple(padding_fields), None, ()
        return "fieldwise_exact", (), None, ()

    def _analyze_record_alignment(
        self,
        decl: Struct,
        *,
        representation_mode: StructRepresentationMode,
        struct_map: dict[str, Struct],
        options: MojoEmitOptions,
    ) -> tuple[int | None, str | None, bool]:
        natural_struct_align = self._natural_struct_field_align(decl, struct_map)
        if natural_struct_align is None:
            natural_struct_align = 1
        align_omit_comment: str | None = None
        align_stride_warning = False
        align_bytes = decl.align_bytes
        valid_mojo_align = mojo_align_decorator_ok(align_bytes)
        explicit_layout_intent = decl.is_packed or decl.requested_align_bytes is not None
        if representation_mode == "opaque_storage_exact":
            natural_struct_align = 1
            explicit_layout_intent = explicit_layout_intent or align_bytes > 1
        if align_bytes < natural_struct_align:
            return None, align_omit_comment, align_stride_warning
        if align_bytes <= natural_struct_align:
            if (
                options.strict_abi
                and align_bytes > 1
                and representation_mode != "opaque_storage_exact"
            ):
                return align_bytes, None, False
            return None, None, False
        if not valid_mojo_align:
            if explicit_layout_intent:
                align_omit_comment = (
                    f"# @align omitted: C align_bytes={align_bytes} is not a valid Mojo @align "
                    "(power of 2, max 2**29)."
                )
            return None, align_omit_comment, False
        return align_bytes, None, False

    def _opaque_storage_for_decl(
        self,
        decl: Struct,
        reasons: tuple[str, ...] | list[str],
    ) -> AnalyzedOpaqueStorage:
        reason_lines = [
            f"# exact C field layout for `{decl.c_name}` is not representable as a typed Mojo struct;",
            "# using opaque byte storage instead.",
        ]
        reason_lines.extend(f"# reason: {reason}" for reason in reasons)
        return AnalyzedOpaqueStorage(
            field_name="storage",
            surface_type_text=f"InlineArray[UInt8, {decl.size_bytes}]",
            size_bytes=decl.size_bytes,
            reason_comment_lines=tuple(reason_lines),
        )

    def _natural_struct_field_align(
        self,
        decl: Struct,
        struct_map: dict[str, Struct],
    ) -> int | None:
        natural_struct_align = 1
        for field in decl.fields:
            layout = self._type_layout(field.type, struct_map, set())
            if layout is None:
                return None
            _, field_align = layout
            natural_struct_align = max(natural_struct_align, field_align)
        return natural_struct_align

    def _type_layout(
        self,
        t: Type,
        struct_map: dict[str, Struct],
        visiting: set[str],
    ) -> tuple[int, int] | None:
        core = peel_wrappers(t)
        if isinstance(core, IntType):
            return core.size_bytes, core.align_bytes or core.size_bytes
        if isinstance(core, FloatType):
            return core.size_bytes, core.align_bytes or core.size_bytes
        if isinstance(core, EnumRef):
            return self._type_layout(core.underlying, struct_map, visiting)
        if isinstance(core, (Pointer, FunctionPtr, OpaqueRecordRef)):
            return _POINTER_SIZE_BYTES, _POINTER_ALIGN_BYTES
        if isinstance(core, UnsupportedType):
            if core.size_bytes is None or core.align_bytes is None:
                return None
            return core.size_bytes, core.align_bytes
        if isinstance(core, ComplexType):
            return core.size_bytes, core.element.align_bytes or core.element.size_bytes
        if isinstance(core, VectorType):
            element_layout = self._type_layout(core.element, struct_map, visiting)
            if element_layout is None:
                return core.size_bytes, core.size_bytes
            _, element_align = element_layout
            return core.size_bytes, max(
                element_align,
                core.size_bytes if core.is_ext_vector else element_align,
            )
        if isinstance(core, StructRef):
            if core.is_union:
                return core.size_bytes, 1
            if core.decl_id in visiting:
                return None
            target = struct_map.get(core.decl_id)
            if target is None:
                return None
            visiting.add(core.decl_id)
            try:
                return target.size_bytes, target.align_bytes
            finally:
                visiting.remove(core.decl_id)
        if isinstance(core, Array):
            if core.array_kind != "fixed" or core.size is None:
                return _POINTER_SIZE_BYTES, _POINTER_ALIGN_BYTES
            element_layout = self._type_layout(core.element, struct_map, visiting)
            if element_layout is None:
                return None
            element_size, element_align = element_layout
            return element_size * core.size, element_align
        if isinstance(core, AtomicType):
            return self._type_layout(core.value_type, struct_map, visiting)
        if isinstance(core, TypeRef):
            return self._type_layout(core.canonical, struct_map, visiting)
        if isinstance(core, QualifiedType):
            return self._type_layout(core.unqualified, struct_map, visiting)
        return None

    @staticmethod
    def _align_up(offset: int, align: int) -> int:
        if align <= 1:
            return offset
        rem = offset % align
        if rem == 0:
            return offset
        return offset + (align - rem)

    def _analyze_field(
        self,
        *,
        decl_id: str,
        field: Field,
        index: int,
        field_callback_aliases: dict[tuple[str, int], str] | None,
        options: MojoEmitOptions,
        type_mapper: TypeMapper,
    ) -> AnalyzedField:
        callback_alias_name = (
            None if field_callback_aliases is None else field_callback_aliases.get((decl_id, index))
        )
        comment_lines: list[str] = []
        if field.is_bitfield:
            backing = (
                scalar_comment_name(field.type)
                if isinstance(field.type, (IntType, FloatType, VoidType))
                else type(field.type).__name__
            )
            comment_lines.append(
                f"# bitfield: C bits {field.bit_offset}..{field.bit_offset + field.bit_width - 1} ({field.bit_width} bits) on {backing}"
            )
            if options.warn_abi:
                comment_lines.append("# ABI: verify bitfield layout matches target C compiler.")
        if callback_alias_name is None and isinstance(field.type, FunctionPtr):
            comment_lines.append(f"# {type_mapper.function_ptr_comment(field.type)}")
        surface_type_text = (
            type_mapper.callback_pointer_type(callback_alias_name)
            if callback_alias_name is not None
            else type_mapper.surface(field.type)
        )
        return AnalyzedField(
            field=field,
            index=index,
            mojo_name=field_mojo_name(field, index),
            surface_type_text=surface_type_text,
            comment_lines=tuple(comment_lines),
        )

    def _analyze_bitfield_layout(
        self,
        analyzed_fields: tuple[AnalyzedField, ...],
        *,
        options: MojoEmitOptions,
        type_mapper: TypeMapper,
    ) -> AnalyzedBitfieldLayout | None:
        storages: list[AnalyzedBitfieldStorage] = []
        members: list[AnalyzedBitfieldMember] = []
        saw_bitfield = False
        current: AnalyzedBitfieldStorage | None = None
        for analyzed_field in analyzed_fields:
            field = analyzed_field.field
            if not field.is_bitfield:
                current = None
                continue
            saw_bitfield = True
            width_bits = bitfield_storage_width_bits(field)
            storage_type = bitfield_unsigned_storage_type(field)
            if width_bits is None or storage_type is None:
                return None
            if field.bit_width == 0:
                current = None
                continue
            field_end_bit = field.bit_offset + field.bit_width
            if current is None:
                needs_new_storage = True
            else:
                assert current is not None
                widened_width_bits = max(current.width_bits, width_bits)
                needs_new_storage = (
                    field.bit_offset < current.start_bit
                    or field_end_bit > current.start_bit + widened_width_bits
                )
            if needs_new_storage:
                storage_start_bit = (field.bit_offset // width_bits) * width_bits
                comment_lines = ()
                if options.warn_abi:
                    comment_lines = (
                        f"# bitfield storage: bits {storage_start_bit}..{storage_start_bit + width_bits - 1} at byte offset {storage_start_bit // 8}",
                    )
                current = AnalyzedBitfieldStorage(
                    name=f"__bf{len(storages)}",
                    type=storage_type,
                    surface_type_text=type_mapper.surface(storage_type),
                    field_index=analyzed_field.index,
                    byte_offset=storage_start_bit // 8,
                    start_bit=storage_start_bit,
                    width_bits=width_bits,
                    comment_lines=comment_lines,
                )
                storages.append(current)
            else:
                assert current is not None
                if width_bits > current.width_bits:
                    current = AnalyzedBitfieldStorage(
                        name=current.name,
                        type=storage_type,
                        surface_type_text=type_mapper.surface(storage_type),
                        field_index=current.field_index,
                        byte_offset=current.byte_offset,
                        start_bit=current.start_bit,
                        width_bits=width_bits,
                        comment_lines=current.comment_lines,
                    )
                    storages[-1] = current
            if field.is_anonymous:
                continue
            comment_lines = ()
            if options.warn_abi:
                comment_lines = (
                    f"# bitfield accessor: C bits {field.bit_offset}..{field.bit_offset + field.bit_width - 1} ({field.bit_width} bits)",
                )
            assert current is not None
            members.append(
                AnalyzedBitfieldMember(
                    field=field,
                    mojo_name=analyzed_field.mojo_name,
                    surface_type_text=type_mapper.surface(field.type),
                    storage_name=current.name,
                    storage_type=current.type,
                    storage_type_text=current.surface_type_text,
                    storage_local_bit_offset=field.bit_offset - current.start_bit,
                    bit_width=field.bit_width,
                    is_signed=bitfield_field_is_signed(field),
                    is_bool=bitfield_field_is_bool(field),
                    comment_lines=comment_lines,
                )
            )
        if not saw_bitfield:
            return None
        return AnalyzedBitfieldLayout(storages=tuple(storages), members=tuple(members))

    def _analyze_struct_initializers(
        self,
        fields: tuple[AnalyzedField, ...],
        bitfield_layout: AnalyzedBitfieldLayout | None,
        type_mapper: TypeMapper,
    ) -> tuple[StructInitKind, tuple[AnalyzedStructInitializer, ...]]:
        if fields or bitfield_layout is None:
            return "fieldwise", ()
        typed_params = tuple(
            AnalyzedStructInitParam(
                name=member.mojo_name,
                type=member.field.type,
                surface_type_text=type_mapper.surface(member.field.type),
            )
            for member in bitfield_layout.members
        )
        initializers = [AnalyzedStructInitializer(params=())]
        if typed_params:
            initializers.append(AnalyzedStructInitializer(params=typed_params))
        return "synthesized", tuple(initializers)


__all__ = ["AnalyzeStructLoweringPass"]

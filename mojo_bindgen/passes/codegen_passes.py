"""Concrete Mojo codegen analysis passes."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

from mojo_bindgen.codegen.mojo_emit_options import FFIScalarStyle, MojoEmitOptions
from mojo_bindgen.codegen.mojo_mapper import FFIOriginStyle, TypeMapper, mojo_ident, peel_wrappers
from mojo_bindgen.ir import (
    Array,
    AtomicType,
    BinaryExpr,
    CastExpr,
    CharLiteral,
    ComplexType,
    Const,
    Enum,
    EnumRef,
    Field,
    FloatLiteral,
    FloatType,
    Function,
    FunctionPtr,
    GlobalVar,
    IntLiteral,
    IntType,
    MacroDecl,
    NullPtrLiteral,
    OpaqueRecordRef,
    Pointer,
    QualifiedType,
    RefExpr,
    StringLiteral,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Typedef,
    UnaryExpr,
    Unit,
    UnsupportedType,
    VectorType,
    VoidType,
)
from mojo_bindgen.passes.codegen_model import (
    AnalyzedBitfieldLayout,
    AnalyzedBitfieldMember,
    AnalyzedBitfieldStorage,
    AnalyzedCallbackAlias,
    AnalyzedConst,
    AnalyzedEnum,
    AnalyzedField,
    AnalyzedFunction,
    AnalyzedGlobalVar,
    AnalyzedMacro,
    AnalyzedOpaqueStorage,
    AnalyzedPaddingField,
    AnalyzedStruct,
    AnalyzedStructInitializer,
    AnalyzedStructInitParam,
    AnalyzedTypedef,
    AnalyzedUnion,
    TailDecl,
)
from mojo_bindgen.passes.semantic.callbacks import CallbackAliasInfo
from mojo_bindgen.passes.semantic.imports import ImportNeeds
from mojo_bindgen.passes.semantic.layout import (
    LayoutFacts,
    bitfield_field_is_bool,
    bitfield_field_is_signed,
    bitfield_storage_width_bits,
    bitfield_unsigned_storage_type,
    struct_has_representable_atomic_storage,
)
from mojo_bindgen.passes.semantic.names import EmissionNameFacts

_MOJO_MAX_ALIGN_BYTES = 1 << 29
_POINTER_SIZE_BYTES = ctypes.sizeof(ctypes.c_void_p)
_POINTER_ALIGN_BYTES = ctypes.alignment(ctypes.c_void_p)


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def mojo_align_decorator_ok(align_bytes: int) -> bool:
    if align_bytes <= 1:
        return False
    if align_bytes > _MOJO_MAX_ALIGN_BYTES:
        return False
    return _is_power_of_two(align_bytes)


def _scalar_comment_name(t: IntType | FloatType | VoidType) -> str:
    if isinstance(t, IntType):
        return t.int_kind.value
    if isinstance(t, FloatType):
        return t.float_kind.value
    return "VOID"


def _mojo_float_literal_text(c_spelling: str) -> str:
    t = c_spelling.rstrip()
    while t and t[-1] in "fFlL":
        t = t[:-1]
    return t


def _field_mojo_name(f: Field, index: int) -> str:
    if f.source_name:
        return mojo_ident(f.source_name)
    if f.name:
        return mojo_ident(f.name)
    return f"_anon_{index}"


@dataclass(frozen=True)
class UnionFacts:
    unions: tuple[AnalyzedUnion, ...]
    union_alias_names: frozenset[str]
    unsafe_union_names: frozenset[str]


class AnalyzeUnionLoweringPass:
    """Analyze union lowering independently of other declaration kinds."""

    def run(
        self,
        unit: Unit,
        *,
        ffi_origin: FFIOriginStyle,
        ffi_scalar_style: FFIScalarStyle = "std_ffi_aliases",
    ) -> UnionFacts:
        unions: list[AnalyzedUnion] = []
        union_alias_names: set[str] = set()
        unsafe_union_names: set[str] = set()
        mapper = TypeMapper(
            ffi_origin=ffi_origin,
            union_alias_names=frozenset(),
            unsafe_union_names=frozenset(),
            typedef_mojo_names=frozenset(),
            callback_signature_names=frozenset(),
            ffi_scalar_style=ffi_scalar_style,
        )
        for decl in unit.decls:
            if not isinstance(decl, Struct) or not decl.is_union or not decl.is_complete:
                continue
            mojo_name = mojo_ident(decl.name.strip() or decl.c_name.strip())
            union_alias_names.add(mojo_name)
            mapped_members: list[str] = []
            supported = True
            for field in decl.fields:
                if isinstance(peel_wrappers(field.type), UnsupportedType):
                    supported = False
                    break
                mapped = mapper.canonical(field.type)
                if mapped == mojo_name or mapped in mapped_members:
                    supported = False
                    break
                mapped_members.append(mapped)
            if supported:
                unsafe_union_names.add(mojo_name)
                comptime_expr_text = f"UnsafeUnion[{', '.join(mapped_members)}]"
                comment_lines = (
                    f"# -- C union `{decl.c_name}` - comptime `{mojo_name}` = UnsafeUnion[...].",
                    f"# C size={decl.size_bytes} bytes, align={decl.align_bytes}.",
                    "# Members (reference only):",
                ) + tuple(
                    f"#   {field.name if field.name else '(anonymous)'}: {mapper.canonical(field.type)}"
                    for field in decl.fields
                ) + ("",)
                unions.append(
                    AnalyzedUnion(
                        decl=decl,
                        mojo_name=mojo_name,
                        kind="unsafe_union",
                        comptime_expr_text=comptime_expr_text,
                        comment_lines=comment_lines,
                        unsafe_member_types=tuple(mapped_members),
                    )
                )
            else:
                comptime_expr_text = f"InlineArray[UInt8, {decl.size_bytes}]"
                comment_lines = (
                    f"# -- C union `{decl.c_name}` lowered as InlineArray[UInt8, {decl.size_bytes}] to preserve layout.",
                    "# It could not be represented as UnsafeUnion[...] with distinct supported member types.",
                    f"# C size={decl.size_bytes} bytes, align={decl.align_bytes}.",
                    "# Members (reference only):",
                ) + tuple(
                    f"#   {field.name if field.name else '(anonymous)'}: {mapper.canonical(field.type)}"
                    for field in decl.fields
                ) + ("",)
                unions.append(
                    AnalyzedUnion(
                        decl=decl,
                        mojo_name=mojo_name,
                        kind="inline_array",
                        comptime_expr_text=comptime_expr_text,
                        comment_lines=comment_lines,
                    )
                )
        return UnionFacts(
            unions=tuple(unions),
            union_alias_names=frozenset(union_alias_names),
            unsafe_union_names=frozenset(unsafe_union_names),
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
                field=f,
                index=i,
                field_callback_aliases=field_callback_aliases,
                options=options,
                type_mapper=type_mapper,
            )
            for i, f in enumerate(decl.fields)
        )
        bitfield_layout = self._analyze_bitfield_layout(all_fields, options=options, type_mapper=type_mapper)
        fields = tuple(af for af in all_fields if not af.field.is_bitfield)
        representation_mode, padding_fields, opaque_storage, layout_notes = self._analyze_record_representation(
            decl,
            fields=fields,
            struct_map=struct_map,
        )
        decorator_lines.extend(layout_notes)
        align_decorator_value, align_omit_comment, align_stride_warning = self._analyze_record_alignment(
            decl,
            representation_mode=representation_mode,
            struct_map=struct_map,
            options=options,
        )
        if align_decorator_value is not None:
            decorator_lines.insert(0, f"@align({align_decorator_value})")
        if align_omit_comment is not None:
            decorator_lines.append(align_omit_comment)
        init_kind, synthesized_initializers = self._analyze_struct_initializers(
            fields, bitfield_layout, type_mapper
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
        str,
        tuple[AnalyzedPaddingField, ...],
        AnalyzedOpaqueStorage | None,
        tuple[str, ...],
    ]:
        if not decl.is_complete:
            return "fieldwise_exact", (), None, ()
        if any(field.is_bitfield for field in decl.fields):
            return "fieldwise_exact", (), None, ()

        placements: list[tuple[int, str, object]] = []
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
                placements.append(
                    (
                        explicit_padding_start,
                        "padding",
                        AnalyzedPaddingField(
                            name=f"__pad{len([item for _, kind, item in placements if kind == 'padding'])}",
                            surface_type_text=f"InlineArray[UInt8, {explicit_padding_bytes}]",
                            byte_offset=explicit_padding_start,
                            byte_count=explicit_padding_bytes,
                            comment_lines=(
                                f"# synthesized padding: bytes {explicit_padding_start}..{c_offset - 1}",
                            ),
                        ),
                    )
                )
            placements.append((c_offset, "field", analyzed_field))
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
                    (f"typed Mojo fields consume {current_offset} bytes, exceeding C size {decl.size_bytes}",),
                ),
                (),
            )

        if current_offset < decl.size_bytes:
            used_padding = True
            placements.append(
                (
                    current_offset,
                    "padding",
                    AnalyzedPaddingField(
                        name=f"__pad{len([item for _, kind, item in placements if kind == 'padding'])}",
                        surface_type_text=f"InlineArray[UInt8, {decl.size_bytes - current_offset}]",
                        byte_offset=current_offset,
                        byte_count=decl.size_bytes - current_offset,
                        comment_lines=(
                            f"# synthesized trailing padding: bytes {current_offset}..{decl.size_bytes - 1}",
                        ),
                    ),
                )
            )

        padding_fields = tuple(item for _, kind, item in placements if kind == "padding")
        if used_padding:
            return "fieldwise_padded_exact", padding_fields, None, ()
        return "fieldwise_exact", (), None, ()

    def _analyze_record_alignment(
        self,
        decl: Struct,
        *,
        representation_mode: str,
        struct_map: dict[str, Struct],
        options: MojoEmitOptions,
    ) -> tuple[int | None, str | None, bool]:
        natural_struct_align = self._natural_struct_field_align(decl, struct_map)
        if natural_struct_align is None:
            natural_struct_align = 1
        align_omit_comment: str | None = None
        align_stride_warning = False
        ab = decl.align_bytes
        valid_mojo_align = mojo_align_decorator_ok(ab)
        explicit_layout_intent = decl.is_packed or decl.requested_align_bytes is not None
        if representation_mode == "opaque_storage_exact":
            natural_struct_align = 1
            explicit_layout_intent = explicit_layout_intent or ab > 1
        if ab < natural_struct_align:
            return None, align_omit_comment, align_stride_warning
        if ab <= natural_struct_align:
            if options.strict_abi and ab > 1 and representation_mode != "opaque_storage_exact":
                return ab, None, False
            return None, None, False
        if not valid_mojo_align:
            if explicit_layout_intent:
                align_omit_comment = (
                    f"# @align omitted: C align_bytes={ab} is not a valid Mojo @align "
                    "(power of 2, max 2**29)."
                )
            return None, align_omit_comment, False
        return ab, None, False

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
            return core.size_bytes, max(element_align, core.size_bytes if core.is_ext_vector else element_align)
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
                _scalar_comment_name(field.type)
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
            mojo_name=_field_mojo_name(field, index),
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
        for af in analyzed_fields:
            field = af.field
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
                    field_index=af.index,
                    byte_offset=storage_start_bit // 8,
                    start_bit=storage_start_bit,
                    width_bits=width_bits,
                    comment_lines=comment_lines,
                )
                storages.append(current)
            elif width_bits > current.width_bits:
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
            members.append(
                AnalyzedBitfieldMember(
                    field=field,
                    mojo_name=af.mojo_name,
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
    ) -> tuple[str, tuple[AnalyzedStructInitializer, ...]]:
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


class AnalyzeTailDeclPass:
    """Analyze non-struct declaration lowering into render-ready facts."""

    def run(
        self,
        unit: Unit,
        *,
        name_facts: EmissionNameFacts,
        callback_info: CallbackAliasInfo,
        layout_facts: LayoutFacts,
        type_mapper: TypeMapper,
    ) -> tuple[tuple[TailDecl, ...], tuple[AnalyzedCallbackAlias, ...]]:
        callback_aliases = tuple(self._analyze_callback_alias(alias, type_mapper) for alias in callback_info.aliases)
        tail_decls: list[TailDecl] = []
        for decl in unit.decls:
            if isinstance(decl, Typedef):
                tail_decls.append(
                    AnalyzedTypedef(
                        decl=decl,
                        skip_duplicate=mojo_ident(decl.name) in name_facts.emitted_names,
                        mojo_name=mojo_ident(decl.name),
                        rhs_text=type_mapper.surface(decl.aliased),
                        callback_alias_name=callback_info.typedef_aliases.get(decl.decl_id),
                    )
                )
            elif isinstance(decl, Function):
                tail_decls.append(
                    self._analyze_function(
                        decl,
                        layout_facts.struct_map,
                        layout_facts.register_passable_by_decl_id,
                        callback_info,
                        type_mapper,
                    )
                )
            elif isinstance(decl, GlobalVar):
                tail_decls.append(self._analyze_global_var(decl, callback_info, type_mapper))
            elif isinstance(decl, Enum):
                tail_decls.append(self._analyze_enum(decl, type_mapper))
            elif isinstance(decl, Const):
                tail_decls.append(self._analyze_const(decl, type_mapper))
            elif isinstance(decl, MacroDecl):
                tail_decls.append(self._analyze_macro(decl, type_mapper))
        return tuple(tail_decls), callback_aliases

    def _analyze_callback_alias(self, alias, type_mapper: TypeMapper) -> AnalyzedCallbackAlias:
        expr = type_mapper.callback_signature_alias_expr(alias.fp)
        if expr is None:
            return AnalyzedCallbackAlias(
                name=alias.name,
                emit_expr_text=None,
                comment_lines=(
                    f"# callback alias {alias.name}: unsupported callback signature shape",
                    f"# {type_mapper.function_ptr_comment(alias.fp)}",
                    "",
                ),
            )
        return AnalyzedCallbackAlias(name=alias.name, emit_expr_text=expr)

    def _analyze_global_var(self, decl: GlobalVar, callback_info: CallbackAliasInfo, type_mapper: TypeMapper) -> AnalyzedGlobalVar:
        callback_alias = callback_info.global_aliases.get(decl.decl_id)
        surface_type = (
            type_mapper.callback_pointer_type(callback_alias)
            if callback_alias is not None
            else type_mapper.surface(decl.type)
        )
        reason = self._global_var_stub_reason(decl)
        return AnalyzedGlobalVar(
            decl=decl,
            kind="stub" if reason is not None else "wrapper",
            surface_type=surface_type,
            mojo_name=mojo_ident(decl.name),
            stub_reason=reason,
        )

    def _global_var_stub_reason(self, decl: GlobalVar) -> str | None:
        t = decl.type
        while True:
            if isinstance(t, AtomicType):
                return "atomic global requires manual binding (use Atomic APIs on a pointer)"
            if isinstance(t, TypeRef):
                t = t.canonical
                continue
            if isinstance(t, QualifiedType):
                t = t.unqualified
                continue
            break
        core = peel_wrappers(decl.type)
        if isinstance(core, UnsupportedType) and (core.size_bytes is None or core.size_bytes == 0):
            return "unsupported global type layout"
        return None

    def _analyze_function(
        self,
        fn: Function,
        struct_map: dict[str, Struct],
        register_passable_by_decl_id: dict[str, bool],
        callback_info: CallbackAliasInfo,
        type_mapper: TypeMapper,
    ) -> AnalyzedFunction:
        param_names = tuple(type_mapper.param_names(fn.params))
        ret_callback_alias_name = callback_info.fn_ret_aliases.get(fn.decl_id)
        param_callback_alias_names = tuple(
            callback_info.fn_param_aliases.get((fn.decl_id, i)) for i in range(len(fn.params))
        )
        kind = "wrapper"
        if fn.is_variadic:
            kind = "variadic_stub"
        else:
            ret_u = peel_wrappers(fn.ret)
            if isinstance(ret_u, StructRef):
                rs = struct_map.get(ret_u.decl_id)
                if rs is not None and not register_passable_by_decl_id.get(rs.decl_id, False):
                    kind = "non_register_return_stub"
        ret_t = (
            type_mapper.callback_pointer_type(ret_callback_alias_name)
            if ret_callback_alias_name is not None
            else type_mapper.signature(fn.ret)
        )
        args_sig = ", ".join(
            f"{name}: {type_mapper.callback_pointer_type(alias) if alias is not None else type_mapper.signature(param.type)}"
            for name, param, alias in zip(param_names, fn.params, param_callback_alias_names, strict=True)
        )
        call_args = ", ".join(param_names)
        ret_abi = type_mapper.canonical(fn.ret)
        is_void = ret_abi == "NoneType"
        ret_list = "NoneType" if is_void else ret_abi
        bracket_inner = type_mapper.function_type_param_list(
            fn,
            ret_list,
            ret_callback_alias_name=ret_callback_alias_name,
            param_callback_alias_names=param_callback_alias_names,
        )
        return AnalyzedFunction(
            decl=fn,
            kind=kind,
            emitted_name=mojo_ident(fn.name),
            param_names=param_names,
            ret_callback_alias_name=ret_callback_alias_name,
            param_callback_alias_names=param_callback_alias_names,
            rendered_return_type_text=ret_t,
            rendered_args_sig=args_sig,
            rendered_call_args=call_args,
            rendered_ret_list_text=ret_list,
            rendered_bracket_inner_text=bracket_inner,
        )

    def _analyze_enum(self, decl: Enum, type_mapper: TypeMapper) -> AnalyzedEnum:
        base = type_mapper.emit_scalar(decl.underlying)
        return AnalyzedEnum(
            decl=decl,
            mojo_name=mojo_ident(decl.name),
            base_text=base,
            comment_line=f"# enum {decl.c_name} - underlying {_scalar_comment_name(decl.underlying)} -> {base} (verify C ABI)",
            enumerants=tuple(
                (mojo_ident(e.name), f"Self({base}({e.value}))") for e in decl.enumerants
            ),
        )

    def _analyze_const(self, decl: Const, type_mapper: TypeMapper) -> AnalyzedConst:
        rendered = self._render_const_expr(decl.expr, decl.type, type_mapper)
        reason = None
        if rendered is None:
            if isinstance(decl.expr, NullPtrLiteral):
                reason = "null pointer macro is not emitted directly"
            else:
                reason = "unsupported constant expression form"
        return AnalyzedConst(
            decl=decl,
            mojo_name=mojo_ident(decl.name),
            rendered_value_text=rendered,
            unsupported_reason=reason,
        )

    def _analyze_macro(self, decl: MacroDecl, type_mapper: TypeMapper) -> AnalyzedMacro:
        body = " ".join(decl.tokens)
        rendered = None
        reason = decl.diagnostic or decl.kind.replace("_", " ")
        if decl.kind == "object_like_supported" and decl.expr is not None and decl.type is not None:
            if isinstance(decl.expr, RefExpr):
                reason = "identifier reference macro is not emitted directly; only literal macros are currently supported"
            else:
                rendered = self._render_const_expr(decl.expr, decl.type, type_mapper)
                if rendered is None:
                    reason = (
                        "null pointer macro is not emitted directly"
                        if isinstance(decl.expr, NullPtrLiteral)
                        else "parsed macro expression is not emitted directly"
                    )
        return AnalyzedMacro(
            decl=decl,
            mojo_name=mojo_ident(decl.name),
            rendered_value_text=rendered,
            reason=reason,
            body_text=body,
        )

    def _render_const_expr(
        self,
        expr: object,
        decl_type: IntType | FloatType | VoidType | object,
        type_mapper: TypeMapper,
    ) -> str | None:
        if isinstance(expr, IntLiteral) and isinstance(decl_type, (IntType, FloatType, VoidType)):
            return f"{type_mapper.emit_scalar(decl_type)}({expr.value})"
        if isinstance(expr, StringLiteral):
            value = expr.value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{value}"'
        if isinstance(expr, CharLiteral):
            value = expr.value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{value}'"
        if isinstance(expr, FloatLiteral):
            return _mojo_float_literal_text(expr.value)
        if isinstance(expr, RefExpr):
            return mojo_ident(expr.name)
        if isinstance(expr, UnaryExpr):
            operand = self._render_const_expr(expr.operand, decl_type, type_mapper)
            return None if operand is None else f"{expr.op}({operand})"
        if isinstance(expr, CastExpr):
            target = expr.target
            if not isinstance(target, IntType):
                return None
            t = type_mapper.emit_scalar(target)
            if isinstance(expr.expr, IntLiteral):
                return f"{t}({expr.expr.value})"
            inner = self._render_const_expr(expr.expr, target, type_mapper)
            return None if inner is None else f"{t}({inner})"
        if isinstance(expr, BinaryExpr):
            lhs = self._render_const_expr(expr.lhs, decl_type, type_mapper)
            rhs = self._render_const_expr(expr.rhs, decl_type, type_mapper)
            return None if lhs is None or rhs is None else f"({lhs} {expr.op} {rhs})"
        if isinstance(expr, NullPtrLiteral):
            return None
        return None

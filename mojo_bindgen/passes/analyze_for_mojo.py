"""Final Mojo semantic assembly pass producing :class:`AnalyzedUnit`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.codegen.mojo_emit_options import FFIScalarStyle, MojoEmitOptions
from mojo_bindgen.codegen.mojo_mapper import (
    FFIOriginStyle,
    TypeMapper,
    mojo_ident,
    peel_wrappers,
)
from mojo_bindgen.ir import (
    AtomicType,
    Const,
    Enum,
    Field,
    FloatType,
    Function,
    FunctionPtr,
    GlobalVar,
    IntType,
    MacroDecl,
    OpaqueRecordRef,
    Pointer,
    QualifiedType,
    Struct,
    StructRef,
    Type,
    Typedef,
    TypeRef,
    Unit,
    UnsupportedType,
)
from mojo_bindgen.passes.semantic.callbacks import (
    CallbackAlias,
    CallbackAliasInfo,
    CollectCallbackAliasesPass,
)
from mojo_bindgen.passes.semantic.imports import (
    CollectSemanticNeedsPass,
    ImportNeeds,
)
from mojo_bindgen.passes.semantic.layout import (
    ComputeLayoutFactsPass,
    bitfield_field_is_bool,
    bitfield_field_is_signed,
    bitfield_unsigned_storage_type,
    bitfield_storage_width_bits,
    build_register_passable_map,
    struct_by_decl_id,
)
from mojo_bindgen.passes.semantic.names import CollectEmissionNamesPass

_MOJO_MAX_ALIGN_BYTES = 1 << 29

# --- Analyzed* IR -----------------------------------------------------------------


@dataclass(frozen=True)
class AnalyzedField:
    """Derived field metadata needed by the renderer."""

    field: Field
    index: int
    mojo_name: str
    callback_alias_name: str | None = None


@dataclass(frozen=True)
class AnalyzedBitfieldStorage:
    """One synthesized physical storage member for a bitfield run."""

    name: str
    type: Type
    field_index: int
    byte_offset: int
    start_bit: int
    width_bits: int


@dataclass(frozen=True)
class AnalyzedBitfieldMember:
    """One logical named bitfield projected onto a synthesized storage member."""

    field: Field
    mojo_name: str
    storage_name: str
    storage_type: Type
    storage_local_bit_offset: int
    bit_width: int
    is_signed: bool
    is_bool: bool


@dataclass(frozen=True)
class AnalyzedBitfieldLayout:
    """Derived storage/member split for the bitfield portions of a struct."""

    storages: tuple[AnalyzedBitfieldStorage, ...]
    members: tuple[AnalyzedBitfieldMember, ...]


@dataclass(frozen=True)
class AnalyzedStruct:
    """Derived struct-level emission decisions."""

    decl: Struct
    register_passable: bool
    align_decorator: int | None
    align_stride_warning: bool
    align_omit_comment: str | None
    fields: tuple[AnalyzedField, ...]
    bitfield_layout: AnalyzedBitfieldLayout | None = None


@dataclass(frozen=True)
class AnalyzedTypedef:
    """Derived typedef policy."""

    decl: Typedef
    skip_duplicate: bool
    callback_alias_name: str | None = None


FunctionKind = Literal["wrapper", "variadic_stub", "non_register_return_stub"]


@dataclass(frozen=True)
class AnalyzedFunction:
    """Derived function emission decisions."""

    decl: Function
    kind: FunctionKind
    param_names: tuple[str, ...]
    ret_callback_alias_name: str | None = None
    param_callback_alias_names: tuple[str | None, ...] = ()


UnionLoweringKind = Literal["unsafe_union", "inline_array"]


@dataclass(frozen=True)
class AnalyzedUnion:
    """Derived union lowering decisions."""

    decl: Struct
    mojo_name: str
    kind: UnionLoweringKind
    unsafe_member_types: tuple[str, ...] = ()


GlobalVarKind = Literal["wrapper", "stub"]


@dataclass(frozen=True)
class AnalyzedGlobalVar:
    """Derived global variable emission policy."""

    decl: GlobalVar
    kind: GlobalVarKind
    """``wrapper``: emit ``GlobalVar`` / ``GlobalConst`` helpers; ``stub``: comment-only."""

    surface_type: str
    """Mojo surface type used for ``GlobalVar[T=..., link=...]`` (wrapper) or comments (stub)."""

    stub_reason: str | None = None


TailDecl = Enum | Const | MacroDecl | AnalyzedGlobalVar | AnalyzedTypedef | AnalyzedFunction


@dataclass(frozen=True)
class AnalyzedUnit:
    """Unit-level semantic analysis for Mojo generation."""

    unit: Unit
    opts: MojoEmitOptions
    needs_opaque_imports: bool
    needs_simd_import: bool
    needs_complex_import: bool
    needs_atomic_import: bool
    needs_global_symbol_helpers: bool
    """True when at least one global uses ``OwnedDLHandle.get_symbol`` (wrapper globals)."""

    semantic_fallback_notes: tuple[str, ...]
    union_alias_names: frozenset[str]
    unsafe_union_names: frozenset[str]
    emitted_typedef_mojo_names: frozenset[str]
    callback_aliases: tuple[CallbackAlias, ...]
    callback_signature_names: frozenset[str]
    global_callback_aliases: dict[str, str]
    ordered_incomplete_structs: tuple[AnalyzedStruct, ...]
    ordered_structs: tuple[AnalyzedStruct, ...]
    unions: tuple[AnalyzedUnion, ...]
    tail_decls: tuple[TailDecl, ...]
    ffi_scalar_import_names: frozenset[str]
    """``c_int`` / ``c_long`` / … imported from ``std.ffi`` (empty when using ``fixed_width``)."""


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def mojo_align_decorator_ok(align_bytes: int) -> bool:
    if align_bytes <= 1:
        return False
    if align_bytes > _MOJO_MAX_ALIGN_BYTES:
        return False
    return _is_power_of_two(align_bytes)
# --- Layout / unions / register passability ----------------------------------------


def _try_unsafe_union_type_list(
    decl: Struct, ffi_origin: FFIOriginStyle, ffi_scalar_style: FFIScalarStyle = "std_ffi_aliases"
) -> list[str] | None:
    if not decl.is_union or not decl.is_complete or not decl.fields:
        return None
    union_name = mojo_ident(decl.name.strip() or decl.c_name.strip())
    mapper = TypeMapper(
        ffi_origin=ffi_origin,
        union_alias_names=frozenset(),
        unsafe_union_names=frozenset(),
        typedef_mojo_names=frozenset(),
        ffi_scalar_style=ffi_scalar_style,
    )
    mapped_members: list[str] = []
    for f in decl.fields:
        if isinstance(peel_wrappers(f.type), UnsupportedType):
            return None
        mapped = mapper.canonical(f.type)
        if mapped == union_name:
            return None
        mapped_members.append(mapped)
    if len(set(mapped_members)) != len(mapped_members):
        return None
    return mapped_members


def analyze_unions(
    unit: Unit, ffi_origin: FFIOriginStyle, ffi_scalar_style: FFIScalarStyle = "std_ffi_aliases"
) -> tuple[tuple[AnalyzedUnion, ...], frozenset[str], frozenset[str]]:
    unions: list[AnalyzedUnion] = []
    union_alias_names: set[str] = set()
    unsafe_union_names: set[str] = set()
    for d in unit.decls:
        if isinstance(d, Struct) and d.is_union:
            if not d.is_complete:
                continue
            mojo_name = mojo_ident(d.name.strip() or d.c_name.strip())
            union_alias_names.add(mojo_name)
            unsafe_member_types = _try_unsafe_union_type_list(d, ffi_origin, ffi_scalar_style)
            if unsafe_member_types is not None:
                unsafe_union_names.add(mojo_name)
                unions.append(
                    AnalyzedUnion(
                        decl=d,
                        mojo_name=mojo_name,
                        kind="unsafe_union",
                        unsafe_member_types=tuple(unsafe_member_types),
                    )
                )
            else:
                unions.append(
                    AnalyzedUnion(
                        decl=d,
                        mojo_name=mojo_name,
                        kind="inline_array",
                    )
                )
    return tuple(unions), frozenset(union_alias_names), frozenset(unsafe_union_names)


def _field_mojo_name(f: Field, index: int) -> str:
    if f.source_name:
        return mojo_ident(f.source_name)
    if f.name:
        return mojo_ident(f.name)
    return f"_anon_{index}"


def _analyze_bitfield_layout(
    analyzed_fields: tuple[AnalyzedField, ...],
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
        if width_bits is None:
            return None
        if storage_type is None:
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
            current = AnalyzedBitfieldStorage(
                name=f"__bf{len(storages)}",
                type=storage_type,
                field_index=af.index,
                byte_offset=storage_start_bit // 8,
                start_bit=storage_start_bit,
                width_bits=width_bits,
            )
            storages.append(current)
        elif width_bits > current.width_bits:
            current = AnalyzedBitfieldStorage(
                name=current.name,
                type=storage_type,
                field_index=current.field_index,
                byte_offset=current.byte_offset,
                start_bit=current.start_bit,
                width_bits=width_bits,
            )
            storages[-1] = current

        if field.is_anonymous:
            continue

        members.append(
            AnalyzedBitfieldMember(
                field=field,
                mojo_name=af.mojo_name,
                storage_name=current.name,
                storage_type=current.type,
                storage_local_bit_offset=field.bit_offset - current.start_bit,
                bit_width=field.bit_width,
                is_signed=bitfield_field_is_signed(field),
                is_bool=bitfield_field_is_bool(field),
            )
        )

    if not saw_bitfield:
        return None
    return AnalyzedBitfieldLayout(storages=tuple(storages), members=tuple(members))


# --- Orchestration -----------------------------------------------------------------


@dataclass
class _SemanticContext:
    """Precomputed facts for one :func:`analyze_unit_semantics` run (module-internal)."""

    options: MojoEmitOptions
    struct_map: dict[str, Struct]
    ordered_struct_decls: tuple[Struct, ...]
    emitted_names: frozenset[str]
    emitted_typedef_names: frozenset[str]
    callback_info: CallbackAliasInfo
    union_alias_names: frozenset[str]
    unsafe_union_names: frozenset[str]
    register_passable_by_decl_id: dict[str, bool]
    import_needs: ImportNeeds
    semantic_fallback_notes: tuple[str, ...]
    type_mapper: TypeMapper


def _analyze_struct(
    decl: Struct,
    struct_map: dict[str, Struct],
    field_callback_aliases: dict[tuple[str, int], str] | None,
    *,
    register_passable: bool,
    options: MojoEmitOptions,
) -> AnalyzedStruct:
    align_decorator: int | None = None
    align_stride_warning = False
    align_omit_comment: str | None = None
    ab = decl.align_bytes
    valid_mojo_align = mojo_align_decorator_ok(ab)
    explicit_layout_intent = decl.is_packed or decl.requested_align_bytes is not None
    should_emit_align = valid_mojo_align and (
        options.strict_abi or explicit_layout_intent
    )
    if should_emit_align:
        align_decorator = ab
        if decl.size_bytes % ab != 0:
            align_stride_warning = True
    elif ab > 1 and explicit_layout_intent and not valid_mojo_align:
        align_omit_comment = f"# @align omitted: C align_bytes={ab} is not a valid Mojo @align (power of 2, max 2**29)."
    if decl.is_packed:
        packed_comment = "# packed record: verify Mojo layout against the target C ABI."
        align_omit_comment = (
            packed_comment
            if align_omit_comment is None
            else f"{align_omit_comment} {packed_comment[2:]}"
        )
    all_fields = tuple(
        AnalyzedField(
            field=f,
            index=i,
            mojo_name=_field_mojo_name(f, i),
            callback_alias_name=(
                None
                if field_callback_aliases is None
                else field_callback_aliases.get((decl.decl_id, i))
            ),
        )
        for i, f in enumerate(decl.fields)
    )
    bitfield_layout = _analyze_bitfield_layout(all_fields)
    fields = tuple(af for af in all_fields if not af.field.is_bitfield)
    return AnalyzedStruct(
        decl=decl,
        register_passable=register_passable,
        align_decorator=align_decorator,
        align_stride_warning=align_stride_warning,
        align_omit_comment=align_omit_comment,
        fields=fields,
        bitfield_layout=bitfield_layout,
    )


def _outer_atomic(t: Type) -> AtomicType | None:
    """Return the outermost :class:`AtomicType` wrapper, if any (before typedef peel)."""

    while True:
        if isinstance(t, AtomicType):
            return t
        if isinstance(t, TypeRef):
            t = t.canonical
            continue
        if isinstance(t, QualifiedType):
            t = t.unqualified
            continue
        return None


def _global_var_stub_reason(decl: GlobalVar) -> str | None:
    """Return a stub reason when thin ``GlobalVar`` wrappers are not emitted."""
    if _outer_atomic(decl.type) is not None:
        return "atomic global requires manual binding (use Atomic APIs on a pointer)"
    core = peel_wrappers(decl.type)
    if isinstance(core, UnsupportedType) and (core.size_bytes is None or core.size_bytes == 0):
        return "unsupported global type layout"
    return None


def _analyze_global_var(
    decl: GlobalVar,
    type_mapper: TypeMapper,
    global_aliases: dict[str, str],
) -> AnalyzedGlobalVar:
    reason = _global_var_stub_reason(decl)
    callback_alias = global_aliases.get(decl.decl_id)
    ty = (
        type_mapper.callback_pointer_type(callback_alias)
        if callback_alias is not None
        else type_mapper.surface(decl.type)
    )
    if reason is not None:
        return AnalyzedGlobalVar(decl=decl, kind="stub", surface_type=ty, stub_reason=reason)
    return AnalyzedGlobalVar(decl=decl, kind="wrapper", surface_type=ty)


def _analyze_function(
    fn: Function,
    struct_map: dict[str, Struct],
    type_mapper: TypeMapper,
    register_passable_by_decl_id: dict[str, bool],
    ret_callback_alias_name: str | None = None,
    param_callback_alias_names: tuple[str | None, ...] = (),
) -> AnalyzedFunction:
    param_names = tuple(type_mapper.param_names(fn.params))
    if fn.is_variadic:
        return AnalyzedFunction(
            decl=fn,
            kind="variadic_stub",
            param_names=param_names,
            ret_callback_alias_name=ret_callback_alias_name,
            param_callback_alias_names=param_callback_alias_names,
        )
    ret_u = peel_wrappers(fn.ret)
    if isinstance(ret_u, StructRef):
        rs = struct_map.get(ret_u.decl_id)
        if rs is not None and not register_passable_by_decl_id.get(rs.decl_id, False):
            return AnalyzedFunction(
                decl=fn,
                kind="non_register_return_stub",
                param_names=param_names,
                ret_callback_alias_name=ret_callback_alias_name,
                param_callback_alias_names=param_callback_alias_names,
            )
    return AnalyzedFunction(
        decl=fn,
        kind="wrapper",
        param_names=param_names,
        ret_callback_alias_name=ret_callback_alias_name,
        param_callback_alias_names=param_callback_alias_names,
    )


def analyze_unit_semantics(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    # Phase A: precompute unit-level semantic facts
    layout_facts = ComputeLayoutFactsPass().run(unit)
    ordered_struct_decls = layout_facts.ordered_structs
    incomplete_struct_decls = layout_facts.incomplete_structs
    name_facts = CollectEmissionNamesPass().run(
        unit,
        ordered_structs=ordered_struct_decls,
        incomplete_structs=incomplete_struct_decls,
    )
    callback_info = CollectCallbackAliasesPass().run(
        unit,
        emitted_typedef_names=name_facts.emitted_typedef_names,
    )
    unions, union_alias_names, unsafe_union_names = analyze_unions(
        unit, options.ffi_origin, options.ffi_scalar_style
    )
    import_needs, semantic_fallback_notes = CollectSemanticNeedsPass().run(unit)
    type_mapper = TypeMapper(
        ffi_origin=options.ffi_origin,
        union_alias_names=union_alias_names,
        unsafe_union_names=unsafe_union_names,
        typedef_mojo_names=name_facts.emitted_typedef_names,
        callback_signature_names=callback_info.signature_names,
        ffi_scalar_style=options.ffi_scalar_style,
    )
    ctx = _SemanticContext(
        options=options,
        struct_map=layout_facts.struct_map,
        ordered_struct_decls=ordered_struct_decls,
        emitted_names=name_facts.emitted_names,
        emitted_typedef_names=name_facts.emitted_typedef_names,
        callback_info=callback_info,
        union_alias_names=union_alias_names,
        unsafe_union_names=unsafe_union_names,
        register_passable_by_decl_id=layout_facts.register_passable_by_decl_id,
        import_needs=import_needs,
        semantic_fallback_notes=semantic_fallback_notes,
        type_mapper=type_mapper,
    )

    # Phase B: materialize analyzed declarations
    ordered_incomplete_structs = tuple(
        _analyze_struct(
            decl,
            ctx.struct_map,
            ctx.callback_info.field_aliases,
            register_passable=ctx.register_passable_by_decl_id.get(decl.decl_id, False),
            options=ctx.options,
        )
        for decl in incomplete_struct_decls
    )
    ordered_structs = tuple(
        _analyze_struct(
            decl,
            ctx.struct_map,
            ctx.callback_info.field_aliases,
            register_passable=ctx.register_passable_by_decl_id.get(decl.decl_id, False),
            options=ctx.options,
        )
        for decl in ctx.ordered_struct_decls
    )

    tail_decls: list[TailDecl] = []
    for d in unit.decls:
        if isinstance(d, Typedef):
            tail_decls.append(
                AnalyzedTypedef(
                    decl=d,
                    skip_duplicate=mojo_ident(d.name) in ctx.emitted_names,
                    callback_alias_name=ctx.callback_info.typedef_aliases.get(d.decl_id),
                )
            )
        elif isinstance(d, Function):
            tail_decls.append(
                _analyze_function(
                    d,
                    ctx.struct_map,
                    ctx.type_mapper,
                    ctx.register_passable_by_decl_id,
                    ret_callback_alias_name=ctx.callback_info.fn_ret_aliases.get(d.decl_id),
                    param_callback_alias_names=tuple(
                        ctx.callback_info.fn_param_aliases.get((d.decl_id, i))
                        for i in range(len(d.params))
                    ),
                )
            )
        elif isinstance(d, GlobalVar):
            tail_decls.append(
                _analyze_global_var(d, ctx.type_mapper, ctx.callback_info.global_aliases)
            )
        elif isinstance(d, (Enum, Const, MacroDecl)):
            tail_decls.append(d)

    needs_global_symbol_helpers = any(
        isinstance(d, AnalyzedGlobalVar) and d.kind == "wrapper" for d in tail_decls
    )

    ctx.type_mapper.warm_ffi_scalar_imports_from_unit(unit)
    ffi_scalar_import_names = ctx.type_mapper.ffi_scalar_import_names

    return AnalyzedUnit(
        unit=unit,
        opts=ctx.options,
        needs_opaque_imports=ctx.import_needs.opaque,
        needs_simd_import=ctx.import_needs.simd,
        needs_complex_import=ctx.import_needs.complex,
        needs_atomic_import=ctx.import_needs.atomic,
        needs_global_symbol_helpers=needs_global_symbol_helpers,
        semantic_fallback_notes=ctx.semantic_fallback_notes,
        union_alias_names=ctx.union_alias_names,
        unsafe_union_names=ctx.unsafe_union_names,
        emitted_typedef_mojo_names=ctx.emitted_typedef_names,
        callback_aliases=ctx.callback_info.aliases,
        callback_signature_names=ctx.callback_info.signature_names,
        global_callback_aliases=ctx.callback_info.global_aliases,
        ordered_incomplete_structs=ordered_incomplete_structs,
        ordered_structs=ordered_structs,
        unions=unions,
        tail_decls=tuple(tail_decls),
        ffi_scalar_import_names=ffi_scalar_import_names,
    )


def analyzed_struct_for_test(
    decl: Struct,
    *,
    struct_by_name: dict[str, Struct],
    options: MojoEmitOptions | None = None,
) -> AnalyzedStruct:
    reg = build_register_passable_map(struct_by_name).get(decl.decl_id, False)
    return _analyze_struct(
        decl,
        struct_by_name,
        None,
        register_passable=reg,
        options=options or MojoEmitOptions(),
    )


def analyze_unit(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    """Run the IR pass pipeline and final semantic analysis over ``unit``."""
    from mojo_bindgen.passes.pipeline import run_ir_passes

    return analyze_unit_semantics(run_ir_passes(unit), options)


class AnalyzeForMojoPass:
    """Produce final Mojo-specific analyzed output from normalized IR."""

    def __init__(self, options: MojoEmitOptions) -> None:
        self._options = options

    def run(self, unit: Unit) -> AnalyzedUnit:
        return analyze_unit_semantics(unit, self._options)

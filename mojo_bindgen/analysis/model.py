"""Typed analyzed model consumed by Mojo code generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.ir import Field, Function, GlobalVar, Struct, Type, Typedef, Unit


@dataclass(frozen=True)
class AnalyzedField:
    """Derived field metadata needed by the renderer."""

    field: Field
    index: int
    mojo_name: str
    surface_type_text: str
    comment_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalyzedBitfieldStorage:
    """One synthesized physical storage member for a bitfield run."""

    name: str
    type: Type
    surface_type_text: str
    field_index: int
    byte_offset: int
    start_bit: int
    width_bits: int
    comment_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalyzedBitfieldMember:
    """One logical named bitfield projected onto a synthesized storage member."""

    field: Field
    mojo_name: str
    surface_type_text: str
    storage_name: str
    storage_type: Type
    storage_type_text: str
    storage_local_bit_offset: int
    bit_width: int
    is_signed: bool
    is_bool: bool
    comment_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalyzedBitfieldLayout:
    """Derived storage/member split for the bitfield portions of a struct."""

    storages: tuple[AnalyzedBitfieldStorage, ...]
    members: tuple[AnalyzedBitfieldMember, ...]


StructInitKind = Literal["fieldwise", "synthesized"]
StructRepresentationMode = Literal[
    "fieldwise_exact",
    "fieldwise_padded_exact",
    "opaque_storage_exact",
]


@dataclass(frozen=True)
class AnalyzedStructInitParam:
    """One surfaced parameter in a synthesized struct initializer."""

    name: str
    type: Type
    surface_type_text: str


@dataclass(frozen=True)
class AnalyzedStructInitializer:
    """One synthesized ``__init__`` overload for a struct."""

    params: tuple[AnalyzedStructInitParam, ...]


@dataclass(frozen=True)
class AnalyzedPaddingField:
    """One synthesized raw-byte padding member used to preserve C layout exactly."""

    name: str
    surface_type_text: str
    byte_offset: int
    byte_count: int
    comment_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalyzedOpaqueStorage:
    """Opaque byte-storage fallback metadata for records that cannot be fieldwise-represented."""

    field_name: str
    surface_type_text: str
    size_bytes: int
    reason_comment_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalyzedStruct:
    """Derived struct-level emission decisions."""

    decl: Struct
    mojo_name: str
    register_passable: bool
    representation_mode: StructRepresentationMode
    align_decorator: int | None
    align_stride_warning: bool
    align_omit_comment: str | None
    header_comment_lines: tuple[str, ...]
    decorator_lines: tuple[str, ...]
    trait_names: tuple[str, ...]
    emit_fieldwise_init: bool
    fields: tuple[AnalyzedField, ...]
    padding_fields: tuple[AnalyzedPaddingField, ...] = ()
    opaque_storage: AnalyzedOpaqueStorage | None = None
    bitfield_layout: AnalyzedBitfieldLayout | None = None
    init_kind: StructInitKind = "fieldwise"
    synthesized_initializers: tuple[AnalyzedStructInitializer, ...] = ()


@dataclass(frozen=True)
class AnalyzedCallbackAlias:
    """Render-ready callback alias."""

    name: str
    emit_expr_text: str | None
    comment_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalyzedTypedef:
    """Derived typedef policy."""

    decl: Typedef
    skip_duplicate: bool
    mojo_name: str
    rhs_text: str
    callback_alias_name: str | None = None


@dataclass(frozen=True)
class AnalyzedEnum:
    """Render-ready enum wrapper facts."""

    decl: object
    mojo_name: str
    base_text: str
    comment_line: str
    enumerants: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class AnalyzedConst:
    """Render-ready constant lowering."""

    decl: object
    mojo_name: str
    rendered_value_text: str | None
    unsupported_reason: str | None = None


@dataclass(frozen=True)
class AnalyzedMacro:
    """Render-ready macro lowering."""

    decl: object
    mojo_name: str
    rendered_value_text: str | None
    reason: str
    body_text: str


FunctionKind = Literal["wrapper", "variadic_stub", "non_register_return_stub"]


@dataclass(frozen=True)
class AnalyzedFunction:
    """Derived function emission decisions."""

    decl: Function
    kind: FunctionKind
    emitted_name: str
    param_names: tuple[str, ...]
    ret_callback_alias_name: str | None = None
    param_callback_alias_names: tuple[str | None, ...] = ()
    rendered_return_type_text: str = "NoneType"
    rendered_args_sig: str = ""
    rendered_call_args: str = ""
    rendered_ret_list_text: str = "NoneType"
    rendered_bracket_inner_text: str = ""


UnionLoweringKind = Literal["unsafe_union", "inline_array"]


@dataclass(frozen=True)
class AnalyzedUnion:
    """Derived union lowering decisions."""

    decl: Struct
    mojo_name: str
    kind: UnionLoweringKind
    comptime_expr_text: str
    comment_lines: tuple[str, ...]
    unsafe_member_types: tuple[str, ...] = ()


GlobalVarKind = Literal["wrapper", "stub"]


@dataclass(frozen=True)
class AnalyzedGlobalVar:
    """Derived global variable emission policy."""

    decl: GlobalVar
    kind: GlobalVarKind
    surface_type: str
    mojo_name: str
    stub_reason: str | None = None


TailDecl = (
    AnalyzedEnum
    | AnalyzedConst
    | AnalyzedMacro
    | AnalyzedGlobalVar
    | AnalyzedTypedef
    | AnalyzedFunction
)


@dataclass(frozen=True)
class AnalyzedUnit:
    """Unit-level semantic analysis for Mojo generation."""

    unit: Unit
    opts: object
    needs_opaque_imports: bool
    needs_simd_import: bool
    needs_complex_import: bool
    needs_atomic_import: bool
    needs_global_symbol_helpers: bool
    semantic_fallback_notes: tuple[str, ...]
    union_alias_names: frozenset[str]
    unsafe_union_names: frozenset[str]
    emitted_typedef_mojo_names: frozenset[str]
    callback_aliases: tuple[AnalyzedCallbackAlias, ...]
    callback_signature_names: frozenset[str]
    global_callback_aliases: dict[str, str]
    ordered_incomplete_structs: tuple[AnalyzedStruct, ...]
    ordered_structs: tuple[AnalyzedStruct, ...]
    unions: tuple[AnalyzedUnion, ...]
    tail_decls: tuple[TailDecl, ...]
    ffi_scalar_import_names: frozenset[str]

# pyright: reportUnsupportedDunderAll=false
"""Immutable recursive CIR and MojoIR payloads. Debug codecs live in serde."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Union


class IntKind(StrEnum):
    """Discriminant for integer-like scalars and character-width integer types."""

    BOOL = "BOOL"
    CHAR_S = "CHAR_S"
    CHAR_U = "CHAR_U"
    SCHAR = "SCHAR"
    UCHAR = "UCHAR"
    SHORT = "SHORT"
    USHORT = "USHORT"
    INT = "INT"
    UINT = "UINT"
    LONG = "LONG"
    ULONG = "ULONG"
    LONGLONG = "LONGLONG"
    ULONGLONG = "ULONGLONG"
    INT128 = "INT128"
    UINT128 = "UINT128"
    WCHAR = "WCHAR"
    CHAR16 = "CHAR16"
    CHAR32 = "CHAR32"
    EXT_INT = "EXT_INT"


class FloatKind(StrEnum):
    """Discriminant for floating-point scalar families."""

    FLOAT16 = "FLOAT16"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    LONG_DOUBLE = "LONG_DOUBLE"
    FLOAT128 = "FLOAT128"


_SIGNED_INT_KINDS = {
    IntKind.CHAR_S,
    IntKind.SCHAR,
    IntKind.SHORT,
    IntKind.INT,
    IntKind.LONG,
    IntKind.LONGLONG,
    IntKind.INT128,
}
_UNSIGNED_INT_KINDS = {
    IntKind.CHAR_U,
    IntKind.UCHAR,
    IntKind.USHORT,
    IntKind.UINT,
    IntKind.ULONG,
    IntKind.ULONGLONG,
    IntKind.UINT128,
}
UnsupportedTypeCategory = Literal[
    "unexposed", "vector", "complex", "block", "objc", "unsupported_extension", "invalid", "unknown"
]
ArrayKind = Literal["fixed", "incomplete", "flexible", "variable"]
FamPattern = Literal["c99_empty", "gnu_zero"]
MacroDeclKind = Literal[
    "object_like_supported",
    "object_like_unsupported",
    "function_like_unsupported",
    "empty",
    "predefined",
    "invalid",
]


class PointerMutability(StrEnum):
    MUT = "mut"
    IMMUT = "immut"


class PointerOrigin(StrEnum):
    EXTERNAL = "external"
    ANY = "any"


class InlineDisposition(StrEnum):
    NONE = "none"
    INLINE = "inline"
    EXTERN_INLINE = "extern_inline"


@dataclass(frozen=True)
class DocComment:
    """Source documentation associated with a C declaration cursor."""

    text: str
    brief: str | None = None
    source: Literal["clang_raw"] = "clang_raw"


class ByteOrder(StrEnum):
    """Target byte order used for storage layout and ABI decisions."""

    LITTLE = "little"
    BIG = "big"


@dataclass(frozen=True)
class Qualifiers:
    """C type qualifiers preserved on pointee types and other referenced types."""

    is_const: bool = False
    is_volatile: bool = False
    is_restrict: bool = False


@dataclass(frozen=True)
class VoidType:
    """The unqualified C ``void`` type."""


@dataclass(frozen=True)
class IntType:
    """Explicit integer-like scalar type with ABI width metadata."""

    int_kind: IntKind
    size_bytes: int
    align_bytes: int | None = None
    ext_bits: int | None = None


@dataclass(frozen=True)
class FloatType:
    """Explicit floating-point scalar type with ABI width metadata."""

    float_kind: FloatKind
    size_bytes: int
    align_bytes: int | None = None


@dataclass(frozen=True)
class QualifiedType:
    """A use-site application of C qualifiers to an underlying structural type."""

    unqualified: CType
    qualifiers: Qualifiers = field(default_factory=Qualifiers)


@dataclass(frozen=True)
class AtomicType:
    """A C11 ``_Atomic(T)`` wrapper around an underlying value type."""

    value_type: CType
    size_bytes: int | None = None
    align_bytes: int | None = None


@dataclass(frozen=True)
class CPointer:
    """
    T*.
    pointee=None means unqualified ``void*`` → emit OpaquePointer directly.
    """

    pointee: CType | None
    size_bytes: int = 0
    align_bytes: int | None = None


@dataclass(frozen=True)
class MojoPointer:
    """
    T*.
    pointee=None means unqualified ``void*`` → emit OpaquePointer directly.
    """

    pointee: MojoType | None
    mutability: PointerMutability = PointerMutability.MUT
    origin: PointerOrigin = PointerOrigin.EXTERNAL
    nullable: bool = False


@dataclass(frozen=True)
class CArray:
    """
    Fixed-size, incomplete, flexible, or variable array.

    ``array_kind`` distinguishes the source construct so later phases do not
    need to infer whether ``size=None`` came from a flexible array member,
    incomplete array, or VLA-like construct.
    """

    element: CType
    size: int | None
    array_kind: ArrayKind = "fixed"
    size_bytes: int = 0
    align_bytes: int | None = None


@dataclass(frozen=True)
class MojoArray:
    """Resolved fixed-size target array, including modeled zero-length tails."""

    element: MojoType
    size: int


@dataclass(frozen=True)
class CFunctionPtr:
    """
    Function pointer type: ret (*)(p0, p1, ...).
    Full ret/params are retained for documentation and future tooling.
    """

    ret: CType
    params: tuple[CParam, ...]
    param_names: tuple[str, ...] | None = None
    is_variadic: bool = False
    calling_convention: str | None = None
    is_noreturn: bool = False
    size_bytes: int = 0
    align_bytes: int | None = None


@dataclass(frozen=True)
class MojoFunctionPtr:
    """Resolved callback signature and attributes used by Mojo emission."""

    ret: MojoType
    params: tuple[MojoParam, ...]
    abi: str = "C"
    thin: bool = True
    raises: bool = False


@dataclass(frozen=True)
class FunctionAttrs:
    inline_disposition: InlineDisposition = InlineDisposition.NONE
    is_noreturn: bool = False


@dataclass(frozen=True)
class OpaqueRecordRef:
    """Reference to a declared-but-incomplete struct or union type.

    This node represents intentionally opaque record handles such as
    ``struct FILE`` or public forward-declared library types. It is distinct
    from :class:`UnsupportedType`, which means the parser saw a type it could
    not model faithfully.
    """

    decl_id: str
    name: str
    c_name: str
    is_union: bool = False
    size_bytes: int | None = None
    align_bytes: int | None = None


@dataclass(frozen=True)
class UnsupportedType:
    """A type that the parser recognized but cannot model faithfully yet.

    Unlike :class:`OpaqueRecordRef`, this means the source type is known but
    unsupported for precise mapping. The category and reason fields make the
    fallback explicit for later diagnostics and renderer policy.
    """

    category: UnsupportedTypeCategory
    spelling: str
    reason: str
    size_bytes: int | None = None
    align_bytes: int | None = None


@dataclass(frozen=True)
class ComplexType:
    """C complex scalar modeled as two primitive lanes.

    The element primitive captures the ABI lane type, while ``size_bytes``
    preserves the exact layout width reported by clang.
    """

    element: FloatType
    size_bytes: int
    align_bytes: int | None = None


@dataclass(frozen=True)
class VectorType:
    """SIMD or compiler-extension vector type.

    This preserves extension vector shapes as structured IR instead of
    collapsing them into unsupported opaque blobs.
    """

    element: CType
    count: int | None
    size_bytes: int
    is_ext_vector: bool = False
    align_bytes: int | None = None


@dataclass(frozen=True)
class StructRef:
    """
    Reference to a struct or union layout by name.

    Full :class:`Struct` definitions live only on :class:`Unit` as declarations;
    field and parameter types use ``StructRef`` so :class:`CType` does not embed
    layouts. ``name`` and ``c_name`` are usually the same C tag; anonymous
    record bodies use a stable parent-scoped synthetic name from the parser.

    Unions carry ``is_union=True`` and ``size_bytes`` so the emitter can map
    by-value unions to ``Array[UInt8, size]`` without a separate lookup.
    """

    decl_id: str
    name: str
    c_name: str
    is_union: bool = False
    size_bytes: int = 0
    align_bytes: int | None = None
    is_anonymous: bool = False


@dataclass(frozen=True)
class EnumRef:
    """Reference to a named enum declaration with its integer ABI type."""

    decl_id: str
    name: str
    c_name: str
    underlying: IntType


@dataclass(frozen=True)
class TypeRef:
    """
    A named reference to a C typedef where the typedef name appears in a type
    position (parameter, field, pointer target, etc.).

    ``canonical`` is the fully resolved :class:`CType` for ABI mapping; the
    typedef ``name`` preserves the C API spelling for readable emission.
    """

    decl_id: str
    name: str
    canonical: CType


@dataclass(frozen=True)
class Field:
    """One member of a struct or union."""

    name: str
    source_name: str
    type: CType
    byte_offset: int
    size_bytes: int = 0
    is_anonymous: bool = False
    is_bitfield: bool = False
    "If True, ``type`` is the backing integer :class:`Primitive` only."
    bit_offset: int = 0
    "Bit offset within the storage unit (from clang). Meaningful if ``is_bitfield``."
    bit_width: int = 0
    "Width in bits. Meaningful if ``is_bitfield``."
    fam_pattern: FamPattern | None = None
    "Flexible-tail pattern when this field is recognized as a FAM-style tail."
    doc: DocComment | None = None


@dataclass(frozen=True)
class Struct:
    """
    Published struct or union, including valid incomplete forward declarations.
    is_union=True means all fields share offset 0; size is the largest member.
    Fields are in declaration order (clang cursor order).
    """

    decl_id: str
    name: str
    c_name: str
    fields: tuple[Field, ...]
    size_bytes: int
    align_bytes: int
    is_union: bool = False
    is_anonymous: bool = False
    is_complete: bool = True
    is_packed: bool = False
    requested_align_bytes: int | None = None
    doc: DocComment | None = None


PRIMITIVES_KINDS = Union[IntKind, FloatKind, VoidType]


@dataclass(frozen=True)
class IntLiteral:
    """Integer constant expression leaf."""

    value: int


@dataclass(frozen=True)
class CFloatLiteral:
    """Floating-point constant expression leaf, preserved as source text."""

    spelling: str


@dataclass(frozen=True)
class MojoFloatLiteral:
    """Mapped floating-point literal value."""

    value: float


@dataclass(frozen=True)
class StringLiteral:
    """String-literal constant expression leaf without surrounding quotes."""

    value: str


@dataclass(frozen=True)
class CharLiteral:
    """Character-literal constant expression leaf without surrounding quotes."""

    value: str


@dataclass(frozen=True)
class CNullPtrLiteral:
    """Null-pointer constant expression leaf."""


@dataclass(frozen=True)
class CRefExpr:
    """Reference to another constant-like symbol in a constant expression."""

    name: str


@dataclass(frozen=True)
class MojoRefExpr:
    """Reference to another constant-like symbol in a constant expression."""

    name: str


@dataclass(frozen=True)
class CUnaryExpr:
    """Unary constant expression such as ``-x`` or ``~x``."""

    op: str
    operand: CConstExpr


@dataclass(frozen=True)
class MojoUnaryExpr:
    """Unary constant expression such as ``-x`` or ``~x``."""

    op: str
    operand: MojoConstExpr


@dataclass(frozen=True)
class CBinaryExpr:
    """Binary constant expression such as ``a | b`` or ``x << 2``."""

    op: str
    lhs: CConstExpr
    rhs: CConstExpr


@dataclass(frozen=True)
class MojoBinaryExpr:
    """Binary constant expression such as ``a | b`` or ``x << 2``."""

    op: str
    lhs: MojoConstExpr
    rhs: MojoConstExpr


@dataclass(frozen=True)
class CCastExpr:
    """Cast applied inside a constant expression."""

    target: CType
    expr: CConstExpr


@dataclass(frozen=True)
class MojoCastExpr:
    """Cast applied inside a constant expression."""

    target: MojoType
    expr: MojoConstExpr


@dataclass(frozen=True)
class CSizeOfExpr:
    """``sizeof(T)`` constant expression."""

    target: CType


@dataclass(frozen=True)
class MojoSizeOfExpr:
    """``sizeof(T)`` constant expression."""

    target: MojoType


@dataclass(frozen=True)
class CCallExpr:
    """Function-style constant expression such as enum constructor calls."""

    callee: CConstExpr
    args: tuple[CConstExpr, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MojoCallExpr:
    """Function-style constant expression such as enum constructor calls."""

    callee: MojoConstExpr
    args: tuple[MojoConstExpr, ...] = field(default_factory=tuple)


type CConstExpr = Union[
    IntLiteral,
    CFloatLiteral,
    StringLiteral,
    CharLiteral,
    CNullPtrLiteral,
    CRefExpr,
    CUnaryExpr,
    CBinaryExpr,
    CCastExpr,
    CSizeOfExpr,
    CCallExpr,
]
type MojoConstExpr = Union[
    IntLiteral,
    MojoFloatLiteral,
    StringLiteral,
    CharLiteral,
    MojoRefExpr,
    MojoUnaryExpr,
    MojoBinaryExpr,
    MojoCastExpr,
    MojoSizeOfExpr,
    MojoCallExpr,
]


@dataclass(frozen=True)
class Enumerant:
    name: str
    c_name: str
    value: int
    enum_decl_id: str | None = None
    doc: DocComment | None = None


@dataclass(frozen=True)
class Enum:
    """
    C enum mapped to a scalar type alias plus typed enumerator constants.

    ``name`` is the primary emitted alias chosen by CIR canonicalization.
    ``alias_names`` are additional collision-free names that should alias the
    primary name at Mojo mapping time.
    ``underlying`` is always IntType (C enum base type is integer).
    """

    decl_id: str
    name: str
    c_name: str
    underlying: IntType
    enumerants: tuple[Enumerant, ...]
    alias_names: tuple[str, ...] = field(default_factory=tuple)
    is_anonymous: bool = False
    doc: DocComment | None = None


@dataclass(frozen=True)
class Typedef:
    """
    typedef <type> <name>.

    ``aliased`` is the direct underlying type (one typedef step), often a
    :class:`TypeRef` when the underlying names another typedef.

    ``canonical`` is the fully unrolled type for ABI layout and for mapping
    inside compound positions (struct fields, function pointer signatures).
    """

    decl_id: str
    name: str
    aliased: CType
    canonical: CType
    doc: DocComment | None = None


@dataclass(frozen=True)
class CParam:
    name: str
    type: CType
    doc: DocComment | None = None


@dataclass(frozen=True)
class MojoParam:
    name: str
    type: MojoType
    doc: DocComment | None = None


@dataclass(frozen=True)
class Function:
    """
    Any top-level C function declaration.
    link_name is the actual symbol: may differ from name after NameMapper.
    is_variadic=True → emitted as a comment block, no body generated.
    """

    name: str
    link_name: str
    ret: CType
    params: tuple[CParam, ...]
    is_variadic: bool = False
    decl_id: str = ""
    calling_convention: str | None = None
    attrs: FunctionAttrs = field(default_factory=FunctionAttrs)
    doc: DocComment | None = None


@dataclass(frozen=True)
class Const:
    """
    Top-level C constant or macro-like declaration with an unevaluated or partly
    evaluated constant expression.

    The ``type`` field is the best-effort declared or inferred type; ``expr``
    preserves the expression shape when full evaluation is not desirable.
    """

    name: str
    type: CType
    expr: CConstExpr
    doc: DocComment | None = None


@dataclass(frozen=True)
class MacroDecl:
    """Source-backed preprocessor macro preserved from the parsed translation unit.

    Macros are preserved even when their replacement list cannot be mapped to
    the supported :class:`CConstExpr` subset. ``tokens`` keeps the original
    replacement spelling, while ``expr`` and ``type`` are populated only for
    macros the parser can structurally understand today.
    """

    name: str
    tokens: tuple[str, ...]
    kind: MacroDeclKind
    expr: CConstExpr | None = None
    type: CType | None = None
    diagnostic: str | None = None
    doc: DocComment | None = None


@dataclass(frozen=True)
class GlobalVar:
    """Top-level variable declaration exposed by the bound library.

    This covers exported globals and ``extern const`` declarations that should
    remain part of the binding surface even when they are not reducible to a
    compile-time constant.
    """

    decl_id: str
    name: str
    link_name: str
    type: CType
    is_const: bool = False
    initializer: CConstExpr | None = None
    doc: DocComment | None = None


@dataclass(frozen=True)
class IRDiagnostic:
    """Parser-side note about a recognized construct that cannot be modeled fully."""

    severity: str
    message: str
    file: str | None = None
    line: int | None = None
    col: int | None = None
    decl_id: str | None = None


@dataclass(frozen=True)
class TargetABI:
    """Target ABI facts derived from the Clang parse configuration."""

    pointer_size_bytes: int
    pointer_align_bytes: int
    byte_order: ByteOrder
    target_triple: str | None = None


type Decl = Union[Function, Struct, Enum, Typedef, Const, MacroDecl, GlobalVar]


@dataclass(frozen=True)
class Unit:
    """One parsed header translation unit plus its declarations and diagnostics."""

    source_header: str
    library: str
    link_name: str
    target_abi: TargetABI
    decls: tuple[Decl, ...] = field(default_factory=tuple)
    diagnostics: tuple[IRDiagnostic, ...] = field(default_factory=tuple)


class MojoBuiltin(StrEnum):
    NONE = "NoneType"
    BOOL = "Bool"
    INT8 = "Int8"
    UINT8 = "UInt8"
    INT128 = "Int128"
    UINT128 = "UInt128"
    FLOAT16 = "Float16"
    C_CHAR = "c_char"
    C_UCHAR = "c_uchar"
    C_SHORT = "c_short"
    C_USHORT = "c_ushort"
    C_INT = "c_int"
    C_UINT = "c_uint"
    C_LONG = "c_long"
    C_ULONG = "c_ulong"
    C_LONG_LONG = "c_long_long"
    C_ULONG_LONG = "c_ulong_long"
    C_FLOAT = "c_float"
    C_DOUBLE = "c_double"
    UNSUPPORTED = "unsupported"


PRIMITIVE_BUILTINS: dict[IntKind | FloatKind | str, MojoBuiltin] = {
    "void": MojoBuiltin.NONE,
    IntKind.BOOL: MojoBuiltin.BOOL,
    IntKind.CHAR_S: MojoBuiltin.C_CHAR,
    IntKind.SCHAR: MojoBuiltin.INT8,
    IntKind.CHAR_U: MojoBuiltin.C_UCHAR,
    IntKind.UCHAR: MojoBuiltin.C_UCHAR,
    IntKind.SHORT: MojoBuiltin.C_SHORT,
    IntKind.USHORT: MojoBuiltin.C_USHORT,
    IntKind.INT: MojoBuiltin.C_INT,
    IntKind.UINT: MojoBuiltin.C_UINT,
    IntKind.LONG: MojoBuiltin.C_LONG,
    IntKind.ULONG: MojoBuiltin.C_ULONG,
    IntKind.LONGLONG: MojoBuiltin.C_LONG_LONG,
    IntKind.ULONGLONG: MojoBuiltin.C_ULONG_LONG,
    FloatKind.FLOAT16: MojoBuiltin.FLOAT16,
    FloatKind.FLOAT: MojoBuiltin.C_FLOAT,
    FloatKind.DOUBLE: MojoBuiltin.C_DOUBLE,
    FloatKind.LONG_DOUBLE: MojoBuiltin.C_DOUBLE,
    FloatKind.FLOAT128: MojoBuiltin.UNSUPPORTED,
}
_INT_DTYPE_TABLE: dict[tuple[bool, int], str] = {
    (True, 1): "DType.int8",
    (False, 1): "DType.uint8",
    (True, 2): "DType.int16",
    (False, 2): "DType.uint16",
    (True, 4): "DType.int32",
    (False, 4): "DType.uint32",
    (True, 8): "DType.int64",
    (False, 8): "DType.uint64",
    (True, 16): "DType.int128",
    (False, 16): "DType.uint128",
}
_FLOAT_DTYPE_TABLE: dict[FloatKind, str] = {
    FloatKind.FLOAT16: "DType.float16",
    FloatKind.FLOAT: "DType.float32",
    FloatKind.DOUBLE: "DType.float64",
}
_MOJO_INT_TYPES = (
    MojoBuiltin.INT8,
    MojoBuiltin.C_CHAR,
    MojoBuiltin.C_UCHAR,
    MojoBuiltin.C_SHORT,
    MojoBuiltin.C_USHORT,
    MojoBuiltin.C_INT,
    MojoBuiltin.C_UINT,
    MojoBuiltin.C_LONG,
    MojoBuiltin.C_ULONG,
    MojoBuiltin.C_LONG_LONG,
    MojoBuiltin.C_ULONG_LONG,
    MojoBuiltin.INT128,
    MojoBuiltin.UINT128,
)


@dataclass(frozen=True)
class PrimitiveDType:
    kind: IntKind | FloatKind
    signed: bool
    dtype: str
    width_bytes: int


class GlobalKind(StrEnum):
    WRAPPER = "wrapper"
    STUB = "stub"


class FunctionKind(StrEnum):
    WRAPPER = "wrapper"
    VARIADIC_STUB = "variadic_stub"
    DIRECTIVE_STUB = "directive_stub"
    NON_REGISTER_RETURN_STUB = "non_register_return_stub"


class LinkMode(StrEnum):
    EXTERNAL_CALL = "external_call"
    OWNED_DL_HANDLE = "owned_dl_handle"


class MappingSeverity(StrEnum):
    NOTE = "note"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class MappingNote:
    severity: MappingSeverity
    message: str
    category: str


@dataclass(frozen=True)
class ModuleImport:
    module: str
    names: tuple[str, ...]


class SupportDeclKind(StrEnum):
    DL_HANDLE_HELPERS = "dl_handle_helpers"
    GLOBAL_SYMBOL_HELPERS = "global_symbol_helpers"
    VARIADIC_HELPERS = "variadic_helpers"


@dataclass(frozen=True)
class SupportDecl:
    kind: SupportDeclKind


@dataclass(frozen=True)
class ModuleDependencies:
    imports: tuple[ModuleImport, ...] = field(default_factory=tuple)
    support_decls: tuple[SupportDecl, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BuiltinType:
    name: MojoBuiltin

    @property
    def text(self) -> str:
        return self.name.value


@dataclass(frozen=True)
class NamedType:
    name: str


class ParametricBase(StrEnum):
    SIMD = "SIMD"
    COMPLEX_SIMD = "ComplexSIMD"
    ATOMIC = "Atomic"
    UNSAFE_UNION = "UnsafeUnion"


@dataclass(frozen=True)
class DTypeArg:
    value: str


@dataclass(frozen=True)
class ConstArg:
    value: int


@dataclass(frozen=True)
class NameArg:
    value: str


@dataclass(frozen=True)
class TypeArg:
    type: MojoType


type ParametricArg = Union[DTypeArg, ConstArg, NameArg, TypeArg]


@dataclass(frozen=True)
class ParametricType:
    base: ParametricBase
    args: tuple[ParametricArg, ...] = field(default_factory=tuple)


type CType = Union[
    VoidType,
    IntType,
    FloatType,
    QualifiedType,
    AtomicType,
    CPointer,
    CArray,
    CFunctionPtr,
    OpaqueRecordRef,
    UnsupportedType,
    ComplexType,
    VectorType,
    StructRef,
    EnumRef,
    TypeRef,
]
type MojoType = Union[
    BuiltinType, NamedType, MojoPointer, MojoArray, MojoFunctionPtr, ParametricType
]


@dataclass(frozen=True)
class StoredMember:
    index: int
    name: str
    type: MojoType
    byte_offset: int
    doc: DocComment | None = None


@dataclass(frozen=True)
class PaddingMember:
    name: str
    size_bytes: int
    byte_offset: int


@dataclass(frozen=True)
class OpaqueStorageMember:
    name: str
    size_bytes: int


@dataclass(frozen=True)
class BitfieldField:
    index: int
    name: str
    logical_type: MojoType
    bit_offset: int
    bit_width: int
    signed: bool
    bool_semantics: bool = False
    doc: DocComment | None = None


@dataclass(frozen=True)
class BitfieldGroupMember:
    storage_name: str
    storage_type: MojoType
    byte_offset: int
    first_index: int
    storage_width_bits: int
    fields: tuple[BitfieldField, ...] = field(default_factory=tuple)


type StructMember = Union[StoredMember, PaddingMember, OpaqueStorageMember, BitfieldGroupMember]


@dataclass(frozen=True)
class ComptimeMember:
    name: str
    type_value: MojoType | None = None
    const_value: MojoConstExpr | None = None


@dataclass(frozen=True)
class InitializerParam:
    name: str
    type: MojoType


@dataclass(frozen=True)
class Initializer:
    params: tuple[InitializerParam, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FlexibleTail:
    field_name: str
    element_type: MojoType
    pattern: str
    byte_offset: int


class StructTraits(StrEnum):
    NOT_MOVABLE = "not Movable"
    COPYABLE = "Copyable"
    IMPLICITLY_COPYABLE = "ImplicitlyCopyable"
    MOVABLE = "Movable"
    REGISTER_PASSABLE = "RegisterPassable"
    TRIVIAL_REGISTER_PASSABLE = "TrivialRegisterPassable"


class StructKind(StrEnum):
    PLAIN = "plain"
    OPAQUE = "opaque"


class MojoPassability(StrEnum):
    MEMORY_ONLY = "memory_only"
    REGISTER_PASSABLE = "register_passable"
    TRIVIAL_REGISTER_PASSABLE = "trivial_register_passable"


class AliasKind(StrEnum):
    TYPE_ALIAS = "type_alias"
    CALLBACK_SIGNATURE = "callback_signature"
    UNION_LAYOUT = "union_layout"
    CONST_VALUE = "const_value"
    MACRO_VALUE = "macro_value"


@dataclass(frozen=True)
class StructDecl:
    name: str
    traits: tuple[StructTraits, ...] = field(default_factory=tuple)
    passability: MojoPassability = MojoPassability.MEMORY_ONLY
    align: int | None = None
    align_decorator: int | None = None
    fieldwise_init: bool = False
    kind: StructKind = StructKind.PLAIN
    members: tuple[StructMember, ...] = field(default_factory=tuple)
    comptime_members: tuple[ComptimeMember, ...] = field(default_factory=tuple)
    initializers: tuple[Initializer, ...] = field(default_factory=tuple)
    flexible_tail: FlexibleTail | None = None
    diagnostics: tuple[MappingNote, ...] = field(default_factory=tuple)
    doc: DocComment | None = None


@dataclass(frozen=True)
class AliasDecl:
    name: str
    kind: AliasKind
    type_value: MojoType | None = None
    const_type: MojoType | None = None
    const_value: MojoConstExpr | None = None
    diagnostics: tuple[MappingNote, ...] = field(default_factory=tuple)
    doc: DocComment | None = None

    def has_payload(self) -> bool:
        return self.type_value is not None or self.const_value is not None

    def has_type_payload(self) -> bool:
        return self.type_value is not None and self.const_value is None

    def has_const_payload(self) -> bool:
        return self.const_value is not None and self.type_value is None


@dataclass(frozen=True)
class CallTarget:
    link_mode: LinkMode
    symbol: str


@dataclass(frozen=True)
class FunctionDecl:
    name: str
    link_name: str
    params: tuple[MojoParam, ...] = field(default_factory=tuple)
    return_type: MojoType = field(default_factory=lambda: BuiltinType(MojoBuiltin.NONE))
    kind: FunctionKind = FunctionKind.WRAPPER
    call_target: CallTarget = field(
        default_factory=lambda: CallTarget(link_mode=LinkMode.EXTERNAL_CALL, symbol="")
    )
    attrs: FunctionAttrs = field(default_factory=FunctionAttrs)
    num_fixed_args: int | None = None
    diagnostics: tuple[MappingNote, ...] = field(default_factory=tuple)
    doc: DocComment | None = None


@dataclass(frozen=True)
class GlobalDecl:
    name: str
    link_name: str
    value_type: MojoType
    is_const: bool = False
    kind: GlobalKind = GlobalKind.WRAPPER
    diagnostics: tuple[MappingNote, ...] = field(default_factory=tuple)
    doc: DocComment | None = None


type MojoDecl = Union[StructDecl, AliasDecl, FunctionDecl, GlobalDecl]


@dataclass(frozen=True)
class MojoModule:
    source_header: str
    library: str
    link_name: str
    link_mode: LinkMode
    library_path_hint: str | None = None
    dependencies: ModuleDependencies = field(default_factory=ModuleDependencies)
    decls: tuple[MojoDecl, ...] = field(default_factory=tuple)


__all__ = [
    "AliasDecl",
    "AliasKind",
    "ArrayKind",
    "AtomicType",
    "BitfieldField",
    "BitfieldGroupMember",
    "BuiltinType",
    "ByteOrder",
    "CArray",
    "CBinaryExpr",
    "CCallExpr",
    "CCastExpr",
    "CConstExpr",
    "CFloatLiteral",
    "CFunctionPtr",
    "CNullPtrLiteral",
    "CParam",
    "CPointer",
    "CRefExpr",
    "CSizeOfExpr",
    "CType",
    "CUnaryExpr",
    "CallTarget",
    "CharLiteral",
    "ComplexType",
    "ComptimeMember",
    "Const",
    "ConstArg",
    "DTypeArg",
    "Decl",
    "DocComment",
    "Enum",
    "EnumRef",
    "Enumerant",
    "FamPattern",
    "Field",
    "FlexibleTail",
    "FloatKind",
    "FloatType",
    "Function",
    "FunctionAttrs",
    "FunctionDecl",
    "FunctionKind",
    "GlobalDecl",
    "GlobalKind",
    "GlobalVar",
    "IRDiagnostic",
    "Initializer",
    "InitializerParam",
    "InlineDisposition",
    "IntKind",
    "IntLiteral",
    "IntType",
    "LinkMode",
    "MacroDecl",
    "MacroDeclKind",
    "MappingNote",
    "MappingSeverity",
    "ModuleDependencies",
    "ModuleImport",
    "MojoArray",
    "MojoBinaryExpr",
    "MojoBuiltin",
    "MojoCallExpr",
    "MojoCastExpr",
    "MojoConstExpr",
    "MojoDecl",
    "MojoFloatLiteral",
    "MojoFunctionPtr",
    "MojoModule",
    "MojoParam",
    "MojoPassability",
    "MojoPointer",
    "MojoRefExpr",
    "MojoSizeOfExpr",
    "MojoType",
    "MojoUnaryExpr",
    "NameArg",
    "NamedType",
    "OpaqueRecordRef",
    "OpaqueStorageMember",
    "PaddingMember",
    "ParametricArg",
    "ParametricBase",
    "ParametricType",
    "PointerMutability",
    "PointerOrigin",
    "PrimitiveDType",
    "QualifiedType",
    "Qualifiers",
    "StoredMember",
    "StringLiteral",
    "Struct",
    "StructDecl",
    "StructKind",
    "StructMember",
    "StructRef",
    "StructTraits",
    "SupportDecl",
    "SupportDeclKind",
    "TargetABI",
    "TypeArg",
    "TypeRef",
    "Typedef",
    "Unit",
    "UnsupportedType",
    "UnsupportedTypeCategory",
    "VectorType",
    "VoidType",
]

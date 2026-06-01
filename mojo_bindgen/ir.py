# pyright: reportUnsupportedDunderAll=false
"""
mojo-bindgen IR (intermediate representation) node definitions.

IR node types (as Python classes / unions in this module):

- Type nodes: `VoidType`, `IntType`, `FloatType`, `QualifiedType`, `AtomicType`,
  `Pointer`, `Array`, `FunctionPtr`, `OpaqueRecordRef`, `UnsupportedType`,
  `ComplexType`, `VectorType`, `StructRef`, `EnumRef`, `TypeRef`
  (union alias: `Type`)
- Constant-expression nodes: `IntLiteral`, `FloatLiteral`, `StringLiteral`,
  `CharLiteral`, `NullPtrLiteral`, `RefExpr`, `UnaryExpr`, `BinaryExpr`, `CastExpr`,
  `SizeOfExpr` (union alias: `ConstExpr`)
- Declaration nodes: `Struct`, `Enum`, `Typedef`, `Function`, `Const`, `MacroDecl`,
  `GlobalVar` (union alias: `Decl`)
- Other: `TargetABI`, `IRDiagnostic`, `Unit`
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import (
    Any,
    ClassVar,
    Literal,
    Union,
)

from mojo_bindgen.serde import SerdeFieldSpec, SerDeMixin, SerdeSpec


# Check for char and wchar_t in the IntKind enum
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
    "unexposed",
    "vector",
    "complex",
    "block",
    "objc",
    "unsupported_extension",
    "invalid",
    "unknown",
]
# Categories for types recognized by the parser but not fully modeled.


ArrayKind = Literal["fixed", "incomplete", "flexible", "variable"]
# Array-shape categories that matter for ABI-faithful lowering.

FamPattern = Literal["c99_empty", "gnu_zero"]
# Flexible-tail field patterns recognized by parser record lowering.


MacroDeclKind = Literal[
    "object_like_supported",
    "object_like_unsupported",
    "function_like_unsupported",
    "empty",
    "predefined",
    "invalid",
]
# Classification of preserved preprocessor macro declarations.


@dataclass(frozen=True)
class DocComment(SerDeMixin):
    """Source documentation associated with a C declaration cursor."""

    text: str
    brief: str | None = None
    source: Literal["clang_raw"] = "clang_raw"


class ByteOrder(StrEnum):
    """Target byte order used for storage layout and ABI decisions."""

    LITTLE = "little"
    BIG = "big"


@dataclass(frozen=True)
class Qualifiers(SerDeMixin):
    """C type qualifiers preserved on pointee types and other referenced types."""

    KIND: ClassVar[str | None] = None

    is_const: bool = False
    is_volatile: bool = False
    is_restrict: bool = False


def _expect_kind(d: dict[str, Any], kind: str) -> None:
    if d.get("kind") != kind:
        raise ValueError(f"expected kind {kind!r}, got {d.get('kind')!r}")


# ─────────────────────────────────────────────
#  Type — recursive type tree
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class VoidType(SerDeMixin):
    """The unqualified C ``void`` type."""


@dataclass(frozen=True)
class IntType(SerDeMixin):
    """Explicit integer-like scalar type with ABI width metadata."""

    int_kind: IntKind
    size_bytes: int
    align_bytes: int | None = None
    ext_bits: int | None = None


@dataclass(frozen=True)
class FloatType(SerDeMixin):
    """Explicit floating-point scalar type with ABI width metadata."""

    float_kind: FloatKind
    size_bytes: int
    align_bytes: int | None = None


@dataclass(frozen=True)
class QualifiedType(SerDeMixin):
    """A use-site application of C qualifiers to an underlying structural type."""

    unqualified: Type
    qualifiers: Qualifiers = field(default_factory=Qualifiers)


@dataclass(frozen=True)
class AtomicType(SerDeMixin):
    """A C11 ``_Atomic(T)`` wrapper around an underlying value type."""

    value_type: Type


@dataclass
class Pointer(SerDeMixin):
    """
    T*.
    pointee=None means unqualified ``void*`` → emit OpaquePointer directly.
    """

    pointee: Type | None  # None == void*
    size_bytes: int = 0
    align_bytes: int | None = None


@dataclass
class Array(SerDeMixin):
    """
    Fixed-size, incomplete, flexible, or variable array.

    ``array_kind`` distinguishes the source construct so later phases do not
    need to infer whether ``size=None`` came from a flexible array member,
    incomplete array, or VLA-like construct.
    """

    element: Type
    size: int | None
    array_kind: ArrayKind = "fixed"
    size_bytes: int = 0
    align_bytes: int | None = None


@dataclass
class FunctionPtr(SerDeMixin):
    """
    Function pointer type: ret (*)(p0, p1, ...).
    Full ret/params are retained for documentation and future tooling.
    """

    ret: Type
    params: list[Type]
    param_names: list[str] | None = None
    is_variadic: bool = False
    calling_convention: str | None = None
    is_noreturn: bool = False
    size_bytes: int = 0
    align_bytes: int | None = None


@dataclass
class OpaqueRecordRef(SerDeMixin):
    """Reference to a declared-but-incomplete struct or union type.

    This node represents intentionally opaque record handles such as
    ``struct FILE`` or public forward-declared library types. It is distinct
    from :class:`UnsupportedType`, which means the parser saw a type it could
    not model faithfully.
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"]),
            "c_name": SerdeFieldSpec(missing_from=lambda d: d["name"]),
            "size_bytes": SerdeFieldSpec(omit_if_default=True),
            "align_bytes": SerdeFieldSpec(omit_if_default=True),
        }
    )

    decl_id: str
    name: str
    c_name: str
    is_union: bool = False
    size_bytes: int | None = None
    align_bytes: int | None = None


@dataclass
class UnsupportedType(SerDeMixin):
    """A type that the parser recognized but cannot model faithfully yet.

    Unlike :class:`OpaqueRecordRef`, this means the source type is known but
    unsupported for precise lowering. The category and reason fields make the
    fallback explicit for later diagnostics and renderer policy.
    """

    category: UnsupportedTypeCategory
    spelling: str
    reason: str
    size_bytes: int | None = None
    align_bytes: int | None = None


@dataclass
class ComplexType(SerDeMixin):
    """C complex scalar modeled as two primitive lanes.

    The element primitive captures the ABI lane type, while ``size_bytes``
    preserves the exact layout width reported by clang.
    """

    element: FloatType
    size_bytes: int
    align_bytes: int | None = None


@dataclass
class VectorType(SerDeMixin):
    """SIMD or compiler-extension vector type.

    This preserves extension vector shapes as structured IR instead of
    collapsing them into unsupported opaque blobs.
    """

    element: Type
    count: int | None
    size_bytes: int
    is_ext_vector: bool = False
    align_bytes: int | None = None


@dataclass(frozen=True)
class StructRef(SerDeMixin):
    """
    Reference to a struct or union layout by name.

    Full :class:`Struct` definitions live only on :class:`Unit` as declarations;
    field and parameter types use ``StructRef`` so :class:`Type` does not embed
    layouts. ``name`` and ``c_name`` are usually the same C tag; anonymous
    record bodies use a stable parent-scoped synthetic name from the parser.

    Unions carry ``is_union=True`` and ``size_bytes`` so the emitter can lower
    by-value unions to ``InlineArray[UInt8, size]`` without a separate lookup.
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"]),
            "size_bytes": SerdeFieldSpec(omit_if_default=True),
            "align_bytes": SerdeFieldSpec(omit_if_default=True),
        }
    )

    decl_id: str
    name: str
    c_name: str
    is_union: bool = False
    size_bytes: int = 0
    align_bytes: int | None = None
    is_anonymous: bool = False


@dataclass(frozen=True)
class EnumRef(SerDeMixin):
    """Reference to a named enum declaration with its integer ABI type."""

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={"decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"])}
    )

    decl_id: str
    name: str
    c_name: str
    underlying: IntType


@dataclass
class TypeRef(SerDeMixin):
    """
    A named reference to a C typedef where the typedef name appears in a type
    position (parameter, field, pointer target, etc.).

    ``canonical`` is the fully resolved :class:`Type` for ABI lowering; the
    typedef ``name`` preserves the C API spelling for readable emission.
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={"decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"])}
    )

    decl_id: str
    name: str
    canonical: Type


# ─────────────────────────────────────────────
#  Decl — top-level declaration nodes
# ─────────────────────────────────────────────


@dataclass
class Field(SerDeMixin):
    """One member of a struct or union."""

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "source_name": SerdeFieldSpec(missing_from=lambda d: d["name"]),
            "size_bytes": SerdeFieldSpec(omit_if_default=True),
            "is_bitfield": SerdeFieldSpec(omit_if_default=True),
            "bit_offset": SerdeFieldSpec(omit_when=lambda _v, obj: not obj.is_bitfield),
            "bit_width": SerdeFieldSpec(omit_when=lambda _v, obj: not obj.is_bitfield),
            "fam_pattern": SerdeFieldSpec(omit_if_default=True),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    name: str
    source_name: str
    type: Type
    byte_offset: int  # from clang Type.get_offset(field_name) // 8
    size_bytes: int = 0
    is_anonymous: bool = False
    is_bitfield: bool = False
    """If True, ``type`` is the backing integer :class:`Primitive` only."""
    bit_offset: int = 0
    """Bit offset within the storage unit (from clang). Meaningful if ``is_bitfield``."""
    bit_width: int = 0
    """Width in bits. Meaningful if ``is_bitfield``."""
    fam_pattern: FamPattern | None = None
    """Flexible-tail pattern when this field is recognized as a FAM-style tail."""
    doc: DocComment | None = None


@dataclass
class Struct(SerDeMixin):
    """
    struct or union — always fully laid out.
    is_union=True means all fields share offset 0; size is the largest member.
    Fields are in declaration order (clang cursor order).
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"]),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    decl_id: str
    name: str  # Mojo name
    c_name: str  # original C name for cross-reference
    fields: list[Field]
    size_bytes: int
    align_bytes: int
    is_union: bool = False
    is_anonymous: bool = False
    is_complete: bool = True
    is_packed: bool = False
    requested_align_bytes: int | None = None
    doc: DocComment | None = None


PRIMITIVES_KINDS = Union[IntKind, FloatKind, VoidType]

# Recursive type nodes (no inline Struct/Bitfield — layouts are Struct decls + Field metadata)
Type = Union[
    VoidType,
    IntType,
    FloatType,
    QualifiedType,
    AtomicType,
    Pointer,
    Array,
    FunctionPtr,
    OpaqueRecordRef,
    UnsupportedType,
    ComplexType,
    VectorType,
    StructRef,
    EnumRef,
    TypeRef,
]


@dataclass(frozen=True)
class IntLiteral(SerDeMixin):
    """Integer constant expression leaf."""

    value: int


@dataclass(frozen=True)
class FloatLiteral(SerDeMixin):
    """Floating-point constant expression leaf, preserved as source text."""

    value: str


@dataclass(frozen=True)
class StringLiteral(SerDeMixin):
    """String-literal constant expression leaf without surrounding quotes."""

    value: str


@dataclass(frozen=True)
class CharLiteral(SerDeMixin):
    """Character-literal constant expression leaf without surrounding quotes."""

    value: str


@dataclass(frozen=True)
class NullPtrLiteral(SerDeMixin):
    """Null-pointer constant expression leaf."""


@dataclass(frozen=True)
class RefExpr(SerDeMixin):
    """Reference to another constant-like symbol in a constant expression."""

    name: str


@dataclass(frozen=True)
class UnaryExpr(SerDeMixin):
    """Unary constant expression such as ``-x`` or ``~x``."""

    op: str
    operand: ConstExpr


@dataclass(frozen=True)
class BinaryExpr(SerDeMixin):
    """Binary constant expression such as ``a | b`` or ``x << 2``."""

    op: str
    lhs: ConstExpr
    rhs: ConstExpr


@dataclass(frozen=True)
class CastExpr(SerDeMixin):
    """Cast applied inside a constant expression."""

    target: Type
    expr: ConstExpr


@dataclass(frozen=True)
class SizeOfExpr(SerDeMixin):
    """``sizeof(T)`` constant expression."""

    target: Type


ConstExpr = Union[
    IntLiteral,
    FloatLiteral,
    StringLiteral,
    CharLiteral,
    NullPtrLiteral,
    RefExpr,
    UnaryExpr,
    BinaryExpr,
    CastExpr,
    SizeOfExpr,
]
# Structured constant-expression subset used by macros, enums, and globals.


@dataclass
class Enumerant(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(fields={"doc": SerdeFieldSpec(omit_if_default=True)})

    name: str  # Mojo-mapped constant name
    c_name: str  # original C name
    value: int
    enum_decl_id: str | None = None
    doc: DocComment | None = None
    KIND: ClassVar[str | None] = None


@dataclass
class Enum(SerDeMixin):
    """
    C enum lowered to a scalar type alias plus typed enumerator constants.

    ``name`` is the primary emitted alias chosen by CIR canonicalization.
    ``alias_names`` are additional collision-free names that should alias the
    primary name at Mojo lowering time.
    ``underlying`` is always IntType (C enum base type is integer).
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"]),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    decl_id: str
    name: str
    c_name: str
    underlying: IntType
    enumerants: list[Enumerant]
    alias_names: list[str] = field(default_factory=list)
    is_anonymous: bool = False
    doc: DocComment | None = None


@dataclass
class Typedef(SerDeMixin):
    """
    typedef <type> <name>.

    ``aliased`` is the direct underlying type (one typedef step), often a
    :class:`TypeRef` when the underlying names another typedef.

    ``canonical`` is the fully unrolled type for ABI layout and for lowering
    inside compound positions (struct fields, function pointer signatures).
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"]),
            "canonical": SerdeFieldSpec(missing_from=lambda d: d["aliased"]),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    decl_id: str
    name: str
    aliased: Type
    canonical: Type
    doc: DocComment | None = None


@dataclass
class Param(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(fields={"doc": SerdeFieldSpec(omit_if_default=True)})

    name: str  # "" for anonymous params
    type: Type
    doc: DocComment | None = None
    KIND: ClassVar[str | None] = None


@dataclass
class Function(SerDeMixin):
    """
    Any top-level C function declaration.
    link_name is the actual symbol: may differ from name after NameMapper.
    is_variadic=True → emitted as a comment block, no body generated.
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        field_order=(
            "decl_id",
            "name",
            "link_name",
            "ret",
            "params",
            "is_variadic",
            "calling_convention",
            "is_noreturn",
            "doc",
        ),
        fields={
            "decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"]),
            "doc": SerdeFieldSpec(omit_if_default=True),
        },
    )

    name: str  # Mojo-mapped name (post NameMapper)
    link_name: str  # original C symbol name (used in external_call)
    ret: Type
    params: list[Param]
    is_variadic: bool = False
    decl_id: str = ""
    calling_convention: str | None = None
    is_noreturn: bool = False
    doc: DocComment | None = None


@dataclass
class Const(SerDeMixin):
    """
    Top-level C constant or macro-like declaration with an unevaluated or partly
    evaluated constant expression.

    The ``type`` field is the best-effort declared or inferred type; ``expr``
    preserves the expression shape when full evaluation is not desirable.
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(fields={"doc": SerdeFieldSpec(omit_if_default=True)})

    name: str
    type: Type
    expr: ConstExpr
    doc: DocComment | None = None


@dataclass
class MacroDecl(SerDeMixin):
    """Source-backed preprocessor macro preserved from the parsed translation unit.

    Macros are preserved even when their replacement list cannot be lowered to
    the supported :class:`ConstExpr` subset. ``tokens`` keeps the original
    replacement spelling, while ``expr`` and ``type`` are populated only for
    macros the parser can structurally understand today.
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "kind": SerdeFieldSpec(json_key="macro_kind"),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    name: str
    tokens: list[str]
    kind: MacroDeclKind
    expr: ConstExpr | None = None
    type: Type | None = None
    diagnostic: str | None = None
    doc: DocComment | None = None


@dataclass
class GlobalVar(SerDeMixin):
    """Top-level variable declaration exposed by the bound library.

    This covers exported globals and ``extern const`` declarations that should
    remain part of the binding surface even when they are not reducible to a
    compile-time constant.
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"]),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    decl_id: str
    name: str
    link_name: str
    type: Type
    is_const: bool = False
    initializer: ConstExpr | None = None
    doc: DocComment | None = None


@dataclass(frozen=True)
class IRDiagnostic(SerDeMixin):
    """Parser-side note about a recognized construct that cannot be modeled fully."""

    severity: str
    message: str
    file: str | None = None
    line: int | None = None
    col: int | None = None
    decl_id: str | None = None
    KIND: ClassVar[str | None] = None


@dataclass(frozen=True)
class TargetABI(SerDeMixin):
    """Target ABI facts derived from the Clang parse configuration."""

    pointer_size_bytes: int
    pointer_align_bytes: int
    byte_order: ByteOrder


Decl = Union[
    Function,
    Struct,
    Enum,
    Typedef,
    Const,
    MacroDecl,
    GlobalVar,
]


@dataclass
class Unit(SerDeMixin):
    """One parsed header translation unit plus its declarations and diagnostics."""

    source_header: str
    library: str  # e.g. "zlib"
    link_name: str  # e.g. "z"  (used in DLHandle)
    target_abi: TargetABI
    decls: list[Decl] = field(default_factory=list)
    diagnostics: list[IRDiagnostic] = field(default_factory=list)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize this unit to a JSON string (default: indented for readability)."""
        return json.dumps(self.to_json_dict(), indent=indent)


_TYPE_FROM_JSON: dict[str, Callable[[dict[str, Any]], Type]] = {
    "VoidType": VoidType.from_json_dict,
    "IntType": IntType.from_json_dict,
    "FloatType": FloatType.from_json_dict,
    "QualifiedType": QualifiedType.from_json_dict,
    "AtomicType": AtomicType.from_json_dict,
    "Pointer": Pointer.from_json_dict,
    "Array": Array.from_json_dict,
    "FunctionPtr": FunctionPtr.from_json_dict,
    "OpaqueRecordRef": OpaqueRecordRef.from_json_dict,
    "UnsupportedType": UnsupportedType.from_json_dict,
    "ComplexType": ComplexType.from_json_dict,
    "VectorType": VectorType.from_json_dict,
    "StructRef": StructRef.from_json_dict,
    "EnumRef": EnumRef.from_json_dict,
    "TypeRef": TypeRef.from_json_dict,
}


def type_from_json(d: dict[str, Any]) -> Type:
    """Deserialize a JSON dict produced by :meth:`Type.to_json_dict` back to a :class:`Type`."""
    kind = d.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"unknown Type kind: {kind!r}")
    try:
        deser = _TYPE_FROM_JSON[kind]
    except KeyError:
        raise ValueError(f"unknown Type kind: {kind!r}") from None
    return deser(d)


_CONST_EXPR_FROM_JSON: dict[str, Callable[[dict[str, Any]], ConstExpr]] = {
    "IntLiteral": IntLiteral.from_json_dict,
    "FloatLiteral": FloatLiteral.from_json_dict,
    "StringLiteral": StringLiteral.from_json_dict,
    "CharLiteral": CharLiteral.from_json_dict,
    "NullPtrLiteral": NullPtrLiteral.from_json_dict,
    "RefExpr": RefExpr.from_json_dict,
    "UnaryExpr": UnaryExpr.from_json_dict,
    "BinaryExpr": BinaryExpr.from_json_dict,
    "CastExpr": CastExpr.from_json_dict,
    "SizeOfExpr": SizeOfExpr.from_json_dict,
}


def const_expr_from_json(d: dict[str, Any]) -> ConstExpr:
    """Deserialize one JSON-encoded constant-expression node."""
    kind = d.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"unknown ConstExpr kind: {kind!r}")
    try:
        deser = _CONST_EXPR_FROM_JSON[kind]
    except KeyError:
        raise ValueError(f"unknown ConstExpr kind: {kind!r}") from None
    return deser(d)


_DECL_FROM_JSON: dict[str, Callable[[dict[str, Any]], Decl]] = {
    "Function": Function.from_json_dict,
    "Struct": Struct.from_json_dict,
    "Enum": Enum.from_json_dict,
    "Typedef": Typedef.from_json_dict,
    "Const": Const.from_json_dict,
    "MacroDecl": MacroDecl.from_json_dict,
    "GlobalVar": GlobalVar.from_json_dict,
}


def decl_from_json(d: dict[str, Any]) -> Decl:
    """Deserialize a JSON dict produced by :meth:`Decl.to_json_dict` back to a :class:`Decl`."""
    kind = d.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"unknown Decl kind: {kind!r}")
    try:
        deser = _DECL_FROM_JSON[kind]
    except KeyError:
        raise ValueError(f"unknown Decl kind: {kind!r}") from None
    return deser(d)


# Keep explicit parser-facing aliases available alongside the widened
# Mojo-facing aliases below.
CType = Type
CConstExpr = ConstExpr

# ─────────────────────────────────────────────
#  Mojo-specific IR nodes
# ─────────────────────────────────────────────


class MojoBuiltin(StrEnum):
    NONE = "NoneType"
    BOOL = "Bool"
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
    IntKind.SCHAR: MojoBuiltin.C_CHAR,
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
class PrimitiveDType(SerDeMixin):
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
    NON_REGISTER_RETURN_STUB = "non_register_return_stub"


class LinkMode(StrEnum):
    EXTERNAL_CALL = "external_call"
    OWNED_DL_HANDLE = "owned_dl_handle"


class PointerMutability(StrEnum):
    MUT = "mut"
    IMMUT = "immut"


class PointerOrigin(StrEnum):
    EXTERNAL = "external"
    ANY = "any"


class LoweringSeverity(StrEnum):
    NOTE = "note"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class LoweringNote(SerDeMixin):
    severity: LoweringSeverity
    message: str
    category: str


@dataclass(frozen=True)
class ModuleImport(SerDeMixin):
    module: str
    names: list[str]


class SupportDeclKind(StrEnum):
    DL_HANDLE_HELPERS = "dl_handle_helpers"
    GLOBAL_SYMBOL_HELPERS = "global_symbol_helpers"


@dataclass(frozen=True)
class SupportDecl(SerDeMixin):
    kind: SupportDeclKind


@dataclass
class ModuleDependencies(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "imports": SerdeFieldSpec(omit_if_default=True),
            "support_decls": SerdeFieldSpec(omit_if_default=True),
        }
    )

    imports: list[ModuleImport] = field(default_factory=list)
    support_decls: list[SupportDecl] = field(default_factory=list)


@dataclass(frozen=True)
class BuiltinType(SerDeMixin):
    name: MojoBuiltin

    @property
    def text(self) -> str:
        return self.name.value


@dataclass(frozen=True)
class NamedType(SerDeMixin):
    name: str


class ParametricBase(StrEnum):
    SIMD = "SIMD"
    COMPLEX_SIMD = "ComplexSIMD"
    ATOMIC = "Atomic"
    UNSAFE_UNION = "UnsafeUnion"


@dataclass(frozen=True)
class DTypeArg(SerDeMixin):
    value: str


@dataclass(frozen=True)
class ConstArg(SerDeMixin):
    value: int


@dataclass(frozen=True)
class NameArg(SerDeMixin):
    value: str


@dataclass(frozen=True)
class TypeArg(SerDeMixin):
    type: MojoType


ParametricArg = Union[DTypeArg, ConstArg, NameArg, TypeArg]


@dataclass
class PointerType(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "origin": SerdeFieldSpec(omit_if_default=True),
            "nullable": SerdeFieldSpec(omit_if_default=True),
        }
    )

    pointee: MojoType | None
    mutability: PointerMutability
    origin: PointerOrigin = PointerOrigin.EXTERNAL
    nullable: bool = False


@dataclass(frozen=True)
class ArrayType(SerDeMixin):
    element: MojoType
    count: int


@dataclass
class ParametricType(SerDeMixin):
    base: ParametricBase
    args: list[ParametricArg] = field(default_factory=list)


@dataclass
class FunctionType(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "thin": SerdeFieldSpec(omit_if_default=True),
            "raises": SerdeFieldSpec(omit_if_default=True),
            "abi": SerdeFieldSpec(omit_if_default=True),
        }
    )

    params: list[MojoParam] = field(default_factory=list)
    ret: MojoType = field(default_factory=lambda: BuiltinType(MojoBuiltin.NONE))
    abi: str = "C"
    thin: bool = True
    raises: bool = False


MojoType = Union[
    Type,
    BuiltinType,
    NamedType,
    PointerType,
    ArrayType,
    ParametricType,
    FunctionType,
]


# Check if those are replacable by CIR directly
@dataclass(frozen=True)
class MojoIntLiteral(SerDeMixin):
    value: int


@dataclass(frozen=True)
class MojoFloatLiteral(SerDeMixin):
    value: float


@dataclass(frozen=True)
class MojoStringLiteral(SerDeMixin):
    value: str


@dataclass(frozen=True)
class MojoCharLiteral(SerDeMixin):
    value: str


@dataclass(frozen=True)
class MojoRefExpr(SerDeMixin):
    name: str


@dataclass(frozen=True)
class MojoUnaryExpr(SerDeMixin):
    op: str
    operand: MojoConstExpr


@dataclass(frozen=True)
class MojoBinaryExpr(SerDeMixin):
    op: str
    lhs: MojoConstExpr
    rhs: MojoConstExpr


@dataclass(frozen=True)
class MojoCastExpr(SerDeMixin):
    target: MojoType
    expr: MojoConstExpr


@dataclass(frozen=True)
class MojoSizeOfExpr(SerDeMixin):
    target: MojoType


@dataclass(frozen=True)
class MojoCallExpr(SerDeMixin):
    callee: MojoConstExpr
    args: list[MojoConstExpr] = field(default_factory=list)


MojoConstExpr = Union[
    ConstExpr,
    MojoIntLiteral,
    MojoFloatLiteral,
    MojoStringLiteral,
    MojoCharLiteral,
    MojoRefExpr,
    MojoUnaryExpr,
    MojoBinaryExpr,
    MojoCastExpr,
    MojoSizeOfExpr,
    MojoCallExpr,
]


# TODO: check if size is needed here
@dataclass(frozen=True)
class StoredMember(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(fields={"doc": SerdeFieldSpec(omit_if_default=True)})

    index: int
    name: str
    type: MojoType
    byte_offset: int
    doc: DocComment | None = None


@dataclass(frozen=True)
class PaddingMember(SerDeMixin):
    name: str
    size_bytes: int
    byte_offset: int


@dataclass(frozen=True)
class OpaqueStorageMember(SerDeMixin):
    name: str
    size_bytes: int


@dataclass(frozen=True)
class BitfieldField(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(fields={"doc": SerdeFieldSpec(omit_if_default=True)})

    index: int
    name: str
    logical_type: MojoType
    bit_offset: int
    bit_width: int
    signed: bool
    bool_semantics: bool = False
    doc: DocComment | None = None


@dataclass
class BitfieldGroupMember(SerDeMixin):
    storage_name: str
    storage_type: MojoType
    byte_offset: int
    first_index: int
    storage_width_bits: int
    fields: list[BitfieldField] = field(default_factory=list)


StructMember = Union[
    StoredMember,
    PaddingMember,
    OpaqueStorageMember,
    BitfieldGroupMember,
]


@dataclass(frozen=True)
class ComptimeMember(SerDeMixin):
    name: str
    type_value: MojoType | None = None
    const_value: MojoConstExpr | None = None


@dataclass(frozen=True)
class InitializerParam(SerDeMixin):
    name: str
    type: MojoType


@dataclass
class Initializer(SerDeMixin):
    params: list[InitializerParam] = field(default_factory=list)


@dataclass(frozen=True)
class FlexibleTail(SerDeMixin):
    field_name: str
    element_type: MojoType
    pattern: str
    byte_offset: int


class StructTraits(StrEnum):
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


@dataclass
class StructDecl(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "kind": SerdeFieldSpec(json_key="struct_kind"),
            "align_decorator": SerdeFieldSpec(omit_if_default=True),
            "passability": SerdeFieldSpec(omit_if_default=True),
            "flexible_tail": SerdeFieldSpec(omit_if_default=True),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    name: str
    traits: list[StructTraits] = field(default_factory=list)
    passability: MojoPassability = MojoPassability.MEMORY_ONLY
    align: int | None = None
    align_decorator: int | None = None
    fieldwise_init: bool = False
    kind: StructKind = StructKind.PLAIN
    members: list[StructMember] = field(default_factory=list)
    comptime_members: list[ComptimeMember] = field(default_factory=list)
    initializers: list[Initializer] = field(default_factory=list)
    flexible_tail: FlexibleTail | None = None
    diagnostics: list[LoweringNote] = field(default_factory=list)
    doc: DocComment | None = None


@dataclass
class AliasDecl(SerDeMixin):
    SERDE = SerdeSpec(
        fields={
            "kind": SerdeFieldSpec(json_key="alias_kind"),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    name: str
    kind: AliasKind
    type_value: MojoType | None = None
    const_type: MojoType | None = None
    const_value: MojoConstExpr | None = None
    diagnostics: list[LoweringNote] = field(default_factory=list)
    doc: DocComment | None = None

    def has_payload(self) -> bool:
        return self.type_value is not None or self.const_value is not None

    def has_type_payload(self) -> bool:
        return self.type_value is not None and self.const_value is None

    def has_const_payload(self) -> bool:
        return self.const_value is not None and self.type_value is None


@dataclass(frozen=True)
class MojoParam(SerDeMixin):
    KIND: ClassVar[str | None] = "Param"
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(fields={"doc": SerdeFieldSpec(omit_if_default=True)})

    name: str
    type: MojoType
    doc: DocComment | None = None


@dataclass(frozen=True)
class CallTarget(SerDeMixin):
    link_mode: LinkMode
    symbol: str


@dataclass
class FunctionDecl(SerDeMixin):
    SERDE = SerdeSpec(
        fields={
            "kind": SerdeFieldSpec(json_key="function_kind"),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    name: str
    link_name: str
    params: list[MojoParam] = field(default_factory=list)
    return_type: MojoType = field(default_factory=lambda: BuiltinType(MojoBuiltin.NONE))
    kind: FunctionKind = FunctionKind.WRAPPER
    call_target: CallTarget = field(
        default_factory=lambda: CallTarget(link_mode=LinkMode.EXTERNAL_CALL, symbol="")
    )
    diagnostics: list[LoweringNote] = field(default_factory=list)
    doc: DocComment | None = None


@dataclass
class GlobalDecl(SerDeMixin):
    SERDE = SerdeSpec(
        fields={
            "kind": SerdeFieldSpec(json_key="global_kind"),
            "doc": SerdeFieldSpec(omit_if_default=True),
        }
    )

    name: str
    link_name: str
    value_type: MojoType
    is_const: bool = False
    kind: GlobalKind = GlobalKind.WRAPPER
    diagnostics: list[LoweringNote] = field(default_factory=list)
    doc: DocComment | None = None


MojoDecl = Union[
    StructDecl,
    AliasDecl,
    FunctionDecl,
    GlobalDecl,
]


@dataclass
class MojoModule(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "library_path_hint": SerdeFieldSpec(omit_if_default=True),
            "dependencies": SerdeFieldSpec(omit_if_default=True),
        }
    )

    source_header: str
    library: str
    link_name: str
    link_mode: LinkMode
    library_path_hint: str | None = None
    dependencies: ModuleDependencies = field(default_factory=ModuleDependencies)
    decls: list[MojoDecl] = field(default_factory=list)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_json_dict(), indent=indent)


_PARAMETRIC_ARG_FROM_JSON: dict[str, Callable[[dict[str, object]], ParametricArg]] = {
    "DTypeArg": DTypeArg.from_json_dict,
    "ConstArg": ConstArg.from_json_dict,
    "NameArg": NameArg.from_json_dict,
    "TypeArg": TypeArg.from_json_dict,
}


def parametric_arg_from_json(d: dict[str, object]) -> ParametricArg:
    kind = d.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"unknown ParametricArg kind: {kind!r}")
    try:
        deser = _PARAMETRIC_ARG_FROM_JSON[kind]
    except KeyError:
        raise ValueError(f"unknown ParametricArg kind: {kind!r}") from None
    return deser(d)


_MOJO_TYPE_FROM_JSON: dict[str, Callable[[dict[str, object]], MojoType]] = {
    **_TYPE_FROM_JSON,
    "BuiltinType": BuiltinType.from_json_dict,
    "NamedType": NamedType.from_json_dict,
    "PointerType": PointerType.from_json_dict,
    "ArrayType": ArrayType.from_json_dict,
    "ParametricType": ParametricType.from_json_dict,
    "FunctionType": FunctionType.from_json_dict,
}


def mojo_type_from_json(d: dict[str, object]) -> MojoType:
    kind = d.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"unknown MojoType kind: {kind!r}")
    try:
        deser = _MOJO_TYPE_FROM_JSON[kind]
    except KeyError:
        raise ValueError(f"unknown MojoType kind: {kind!r}") from None
    return deser(d)


_MOJO_CONST_EXPR_FROM_JSON: dict[str, Callable[[dict[str, object]], MojoConstExpr]] = {
    **_CONST_EXPR_FROM_JSON,
    "MojoIntLiteral": MojoIntLiteral.from_json_dict,
    "MojoFloatLiteral": MojoFloatLiteral.from_json_dict,
    "MojoStringLiteral": MojoStringLiteral.from_json_dict,
    "MojoCharLiteral": MojoCharLiteral.from_json_dict,
    "MojoRefExpr": MojoRefExpr.from_json_dict,
    "MojoUnaryExpr": MojoUnaryExpr.from_json_dict,
    "MojoBinaryExpr": MojoBinaryExpr.from_json_dict,
    "MojoCastExpr": MojoCastExpr.from_json_dict,
    "MojoSizeOfExpr": MojoSizeOfExpr.from_json_dict,
    "MojoCallExpr": MojoCallExpr.from_json_dict,
}


def mojo_const_expr_from_json(d: dict[str, object]) -> MojoConstExpr:
    kind = d.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"unknown MojoConstExpr kind: {kind!r}")
    try:
        deser = _MOJO_CONST_EXPR_FROM_JSON[kind]
    except KeyError:
        raise ValueError(f"unknown MojoConstExpr kind: {kind!r}") from None
    return deser(d)


_COMPTIME_MEMBER_FROM_JSON: dict[str, Callable[[dict[str, object]], ComptimeMember]] = {
    "ComptimeMember": ComptimeMember.from_json_dict,
}


def comptime_member_from_json(d: dict[str, object]) -> ComptimeMember:
    kind = d.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"unknown ComptimeMember kind: {kind!r}")
    try:
        deser = _COMPTIME_MEMBER_FROM_JSON[kind]
    except KeyError:
        raise ValueError(f"unknown ComptimeMember kind: {kind!r}") from None
    return deser(d)


_STRUCT_MEMBER_FROM_JSON: dict[str, Callable[[dict[str, object]], StructMember]] = {
    "StoredMember": StoredMember.from_json_dict,
    "PaddingMember": PaddingMember.from_json_dict,
    "OpaqueStorageMember": OpaqueStorageMember.from_json_dict,
    "BitfieldGroupMember": BitfieldGroupMember.from_json_dict,
}


def struct_member_from_json(d: dict[str, object]) -> StructMember:
    kind = d.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"unknown StructMember kind: {kind!r}")
    try:
        deser = _STRUCT_MEMBER_FROM_JSON[kind]
    except KeyError:
        raise ValueError(f"unknown StructMember kind: {kind!r}") from None
    return deser(d)


_MOJO_DECL_FROM_JSON: dict[str, Callable[[dict[str, object]], MojoDecl]] = {
    "StructDecl": StructDecl.from_json_dict,
    "AliasDecl": AliasDecl.from_json_dict,
    "FunctionDecl": FunctionDecl.from_json_dict,
    "GlobalDecl": GlobalDecl.from_json_dict,
}


def mojo_decl_from_json(d: dict[str, object]) -> MojoDecl:
    kind = d.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"unknown MojoDecl kind: {kind!r}")
    try:
        deser = _MOJO_DECL_FROM_JSON[kind]
    except KeyError:
        raise ValueError(f"unknown MojoDecl kind: {kind!r}") from None
    return deser(d)


_MOJO_EXPORTS = [
    "AliasDecl",
    "AliasKind",
    "ArrayType",
    "BitfieldField",
    "BitfieldGroupMember",
    "BuiltinType",
    "CallTarget",
    "ComptimeMember",
    "ConstArg",
    "DTypeArg",
    "FunctionDecl",
    "FunctionKind",
    "FunctionType",
    "GlobalDecl",
    "GlobalKind",
    "Initializer",
    "InitializerParam",
    "LinkMode",
    "LoweringNote",
    "ModuleImport",
    "ModuleDependencies",
    "MojoBinaryExpr",
    "MojoBuiltin",
    "MojoCallExpr",
    "MojoCastExpr",
    "MojoCharLiteral",
    "MojoConstExpr",
    "MojoDecl",
    "MojoFloatLiteral",
    "MojoIntLiteral",
    "MojoModule",
    "MojoPassability",
    "MojoRefExpr",
    "MojoSizeOfExpr",
    "MojoStringLiteral",
    "MojoType",
    "MojoUnaryExpr",
    "NameArg",
    "NamedType",
    "OpaqueStorageMember",
    "PaddingMember",
    "MojoParam",
    "ParametricArg",
    "ParametricBase",
    "ParametricType",
    "PointerMutability",
    "PointerOrigin",
    "PointerType",
    "PRIMITIVE_BUILTINS",
    "StoredMember",
    "StructDecl",
    "StructKind",
    "StructMember",
    "SupportDecl",
    "SupportDeclKind",
    "TypeArg",
    "comptime_member_from_json",
    "mojo_const_expr_from_json",
    "mojo_decl_from_json",
    "mojo_type_from_json",
    "parametric_arg_from_json",
    "struct_member_from_json",
]


# Backwards-compatible spelling for older callers that used the MojoIR parameter name.
MojoIRParam = MojoParam

# Public widened aliases. Parser and CIR analysis can still use Type/ConstExpr
# for the C-only subset; Mojo-facing analysis and codegen use MojoType/MojoConstExpr.
UnifiedType = Union[
    CType,
    BuiltinType,
    NamedType,
    PointerType,
    ArrayType,
    ParametricType,
    FunctionType,
]
UnifiedConstExpr = Union[
    CConstExpr,
    MojoIntLiteral,
    MojoFloatLiteral,
    MojoStringLiteral,
    MojoCharLiteral,
    MojoRefExpr,
    MojoUnaryExpr,
    MojoBinaryExpr,
    MojoCastExpr,
    MojoSizeOfExpr,
    MojoCallExpr,
]
IRDecl = Union[Decl, MojoDecl]

__all__ = [
    "AliasDecl",
    "AliasKind",
    "Array",
    "ArrayKind",
    "ArrayType",
    "AtomicType",
    "BinaryExpr",
    "BitfieldField",
    "BitfieldGroupMember",
    "BuiltinType",
    "ByteOrder",
    "CConstExpr",
    "CType",
    "CallTarget",
    "CastExpr",
    "CharLiteral",
    "ComplexType",
    "ComptimeMember",
    "Const",
    "ConstArg",
    "ConstExpr",
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
    "FloatLiteral",
    "FloatType",
    "Function",
    "FunctionDecl",
    "FunctionKind",
    "FunctionPtr",
    "FunctionType",
    "GlobalDecl",
    "GlobalKind",
    "GlobalVar",
    "IRDecl",
    "IRDiagnostic",
    "Initializer",
    "InitializerParam",
    "IntKind",
    "IntLiteral",
    "IntType",
    "LinkMode",
    "LoweringNote",
    "LoweringSeverity",
    "MacroDecl",
    "MacroDeclKind",
    "ModuleDependencies",
    "ModuleImport",
    "MojoBinaryExpr",
    "MojoBuiltin",
    "MojoCallExpr",
    "MojoCastExpr",
    "MojoCharLiteral",
    "MojoConstExpr",
    "MojoDecl",
    "MojoFloatLiteral",
    "MojoIRParam",
    "MojoIntLiteral",
    "MojoModule",
    "MojoParam",
    "MojoPassability",
    "MojoRefExpr",
    "MojoSizeOfExpr",
    "MojoStringLiteral",
    "MojoType",
    "MojoUnaryExpr",
    "NameArg",
    "NamedType",
    "NullPtrLiteral",
    "OpaqueRecordRef",
    "OpaqueStorageMember",
    "PRIMITIVE_BUILTINS",
    "PRIMITIVES_KINDS",
    "PaddingMember",
    "Param",
    "ParametricArg",
    "ParametricBase",
    "ParametricType",
    "Pointer",
    "PointerMutability",
    "PointerOrigin",
    "PointerType",
    "PrimitiveDType",
    "QualifiedType",
    "Qualifiers",
    "RefExpr",
    "SizeOfExpr",
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
    "Type",
    "TypeArg",
    "TypeRef",
    "Typedef",
    "UnaryExpr",
    "UnifiedConstExpr",
    "UnifiedType",
    "Unit",
    "UnsupportedType",
    "UnsupportedTypeCategory",
    "VectorType",
    "VoidType",
    "comptime_member_from_json",
    "const_expr_from_json",
    "decl_from_json",
    "mojo_const_expr_from_json",
    "mojo_decl_from_json",
    "mojo_type_from_json",
    "parametric_arg_from_json",
    "struct_member_from_json",
    "type_from_json",
]

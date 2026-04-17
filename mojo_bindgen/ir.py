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
- Other: `IRDiagnostic`, `Unit`
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import (
    Any,
    Callable,
    ClassVar,
    Literal,
    Self,
    Union,
)
from mojo_bindgen.serde import SerDeMixin, SerdeFieldSpec, SerdeSpec

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
        }
    )

    decl_id: str
    name: str
    c_name: str
    is_union: bool = False


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
        fields={"decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"])}
    )

    decl_id: str
    name: str
    c_name: str
    is_union: bool = False
    size_bytes: int = 0
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
            "is_bitfield": SerdeFieldSpec(omit_if_default=True),
            "bit_offset": SerdeFieldSpec(omit_when=lambda _v, obj: not obj.is_bitfield),
            "bit_width": SerdeFieldSpec(omit_when=lambda _v, obj: not obj.is_bitfield),
        }
    )

    name: str
    source_name: str
    type: Type
    byte_offset: int  # from clang Type.get_offset(field_name) // 8
    is_anonymous: bool = False
    is_bitfield: bool = False
    """If True, ``type`` is the backing integer :class:`Primitive` only."""
    bit_offset: int = 0
    """Bit offset within the storage unit (from clang). Meaningful if ``is_bitfield``."""
    bit_width: int = 0
    """Width in bits. Meaningful if ``is_bitfield``."""

@dataclass
class Struct(SerDeMixin):
    """
    struct or union — always fully laid out.
    is_union=True means all fields share offset 0; size is the largest member.
    Fields are in declaration order (clang cursor order).
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={"decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"])}
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
    name: str  # Mojo-mapped constant name
    c_name: str  # original C name
    value: int
    KIND: ClassVar[str | None] = None


@dataclass
class Enum(SerDeMixin):
    """
    C enum.  Emitted as a thin struct:
        @fieldwise_init
        struct EnumName(Copyable, Movable, RegisterPassable):
            var value: <underlying Mojo int>
            comptime MEMBER = Self(<underlying>(value))
    underlying is always IntType (C enum base type is integer).
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={"decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"])}
    )

    decl_id: str
    name: str
    c_name: str
    underlying: IntType
    enumerants: list[Enumerant]


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
        }
    )

    decl_id: str
    name: str
    aliased: Type
    canonical: Type


@dataclass
class Param(SerDeMixin):
    name: str  # "" for anonymous params
    type: Type
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
        ),
        fields={"decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"])},
    )

    name: str  # Mojo-mapped name (post NameMapper)
    link_name: str  # original C symbol name (used in external_call)
    ret: Type
    params: list[Param]
    is_variadic: bool = False
    decl_id: str = ""
    calling_convention: str | None = None
    is_noreturn: bool = False


@dataclass
class Const(SerDeMixin):
    """
    Top-level C constant or macro-like declaration with an unevaluated or partly
    evaluated constant expression.

    The ``type`` field is the best-effort declared or inferred type; ``expr``
    preserves the expression shape when full evaluation is not desirable.
    """

    name: str
    type: Type
    expr: ConstExpr


@dataclass
class MacroDecl(SerDeMixin):
    """Top-level preprocessor macro preserved from the primary header.

    Macros are preserved even when their replacement list cannot be lowered to
    the supported :class:`ConstExpr` subset. ``tokens`` keeps the original
    replacement spelling, while ``expr`` and ``type`` are populated only for
    macros the parser can structurally understand today.
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={"kind": SerdeFieldSpec(json_key="macro_kind")}
    )

    name: str
    tokens: list[str]
    kind: MacroDeclKind
    expr: ConstExpr | None = None
    type: Type | None = None
    diagnostic: str | None = None


@dataclass
class GlobalVar(SerDeMixin):
    """Top-level variable declaration exposed by the bound library.

    This covers exported globals and ``extern const`` declarations that should
    remain part of the binding surface even when they are not reducible to a
    compile-time constant.
    """

    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={"decl_id": SerdeFieldSpec(missing_from=lambda d: d["name"])}
    )

    decl_id: str
    name: str
    link_name: str
    type: Type
    is_const: bool = False
    initializer: ConstExpr | None = None


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

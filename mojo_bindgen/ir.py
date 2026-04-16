"""
mojo-bindgen IR (intermediate representation) node definitions.

IR node types (as Python classes / unions in this module):

- Type nodes: `Primitive`, `Pointer`, `Array`, `FunctionPtr`, `OpaqueRecordRef`,
  `UnsupportedType`, `ComplexType`, `VectorType`, `StructRef`, `EnumRef`, `TypeRef`
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
from dataclasses import MISSING, dataclass, field, fields
from enum import StrEnum
from typing import (
    Any,
    Callable,
    ClassVar,
    Literal,
    Self,
    Union,
    cast,
    get_args,
    get_origin,
)


def _encode_json_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, StrEnum):
        return v.value
    to_json_dict = getattr(v, "to_json_dict", None)
    if callable(to_json_dict):
        return to_json_dict()
    if isinstance(v, list):
        return [_encode_json_value(x) for x in v]
    return v


def _decode_list(raw: Any, elem_type: Any) -> Any:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise TypeError(f"expected list, got {type(raw).__name__}")
    out: list[Any] = []
    for x in raw:
        out.append(_decode_json_value(x, elem_type))
    return out


def _decode_json_value(raw: Any, annotated_type: Any) -> Any:
    if raw is None:
        return None

    origin = get_origin(annotated_type)
    if origin is list:
        (elem_type,) = get_args(annotated_type) or (Any,)
        return _decode_list(raw, elem_type)

    # Dataclass-ish nodes (non-union) with from_json_dict.
    from_json_dict = getattr(annotated_type, "from_json_dict", None)
    if callable(from_json_dict) and isinstance(raw, dict):
        return from_json_dict(raw)

    # For discriminated union nodes (Type / Decl / ConstExpr), callers must
    # provide an explicit converter via field metadata; otherwise we keep the
    # error loud so we don't silently mis-decode.
    if isinstance(raw, dict) and "kind" in raw:
        raise TypeError(
            f"missing decoder for discriminated object kind={raw.get('kind')!r}"
        )

    return raw


class SerDeMixin:
    """
    Shared JSON serialization/deserialization mixin for IR dataclasses.

    Strict schema note: dict insertion order is preserved, so we keep `kind`
    first (when present) and then emit keys in either dataclass-field order or
    an explicit `__json_field_order__` override.
    """

    KIND: ClassVar[str | None] = None
    __json_field_order__: ClassVar[list[str] | None] = (
        None  # JSON keys, excluding "kind"
    )

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        kind = getattr(self, "KIND", None)
        if kind is not None:
            out["kind"] = kind

        f_by_json_key: dict[str, Any] = {}
        for f in fields(cast(Any, self)):
            if f.metadata.get("json_exclude", False):
                continue
            json_key = f.metadata.get("json_key", f.name)
            f_by_json_key[json_key] = f

        json_order = getattr(self, "__json_field_order__", None)
        if json_order is None:
            json_order = [
                (f.metadata.get("json_key", f.name))
                for f in fields(cast(Any, self))
                if not f.metadata.get("json_exclude", False)
            ]

        for json_key in json_order:
            f = f_by_json_key[json_key]
            v = getattr(self, f.name)
            to_json = f.metadata.get("to_json")
            if callable(to_json):
                out[json_key] = to_json(v)
            else:
                out[json_key] = _encode_json_value(v)
        return out

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        kind = getattr(cls, "KIND", None)
        if kind is not None:
            _expect_kind(d, kind)

        kwargs: dict[str, Any] = {}
        for f in fields(cast(Any, cls)):
            if f.metadata.get("json_exclude", False):
                continue

            json_key = f.metadata.get("json_key", f.name)
            if json_key in d:
                raw = d[json_key]
            else:
                missing = f.metadata.get("json_missing")
                if callable(missing):
                    raw = missing(d)
                elif f.default is not MISSING or f.default_factory is not MISSING:  # type: ignore[comparison-overlap]
                    continue
                else:
                    raise KeyError(json_key)

            from_json = f.metadata.get("from_json")
            if callable(from_json):
                try:
                    kwargs[f.name] = from_json(raw, d)
                except TypeError:
                    kwargs[f.name] = from_json(raw)
            else:
                kwargs[f.name] = _decode_json_value(raw, f.type)
        return cls(**kwargs)  # type: ignore[call-arg]


class PrimitiveKind(StrEnum):
    """Discriminant for C scalars; JSON-serializes to the enum value string."""

    INT = "INT"
    CHAR = "CHAR"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    VOID = "VOID"


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
    __json_field_order__: ClassVar[list[str] | None] = [
        "is_const",
        "is_volatile",
        "is_restrict",
    ]

    is_const: bool = False
    is_volatile: bool = False
    is_restrict: bool = False


def _expect_kind(d: dict[str, Any], kind: str) -> None:
    if d.get("kind") != kind:
        raise ValueError(f"expected kind {kind!r}, got {d.get('kind')!r}")


# ─────────────────────────────────────────────
#  Type — recursive type tree
# ─────────────────────────────────────────────


@dataclass
class Primitive(SerDeMixin):
    """
    Any scalar C type that maps directly to a Mojo built-in.
    size_bytes comes from clang Type.get_size() — never hardcoded.
    Typical values are 0 (void), 1–8 for integers/bool, often 16 for
    long double / __int128; half-precision (_Float16) uses the size the
    target ABI reports.

    kind classifies the scalar for lowering (e.g. Mojo ``char`` vs ``Int8``).

    is_signed: for kind INT, signed vs unsigned integer. For kind CHAR, reflects
    implementation-defined signedness of plain ``char`` (CHAR_S vs CHAR_U from
    clang). Unused (False) for FLOAT, BOOL, VOID.
    """

    name: str  # canonical C spelling: "unsigned int", "long long", ...
    kind: PrimitiveKind = field(
        metadata={
            "json_key": "primitive_kind",
            "to_json": lambda k: k.value,
            "from_json": lambda raw: PrimitiveKind(raw),
        }
    )
    is_signed: bool
    size_bytes: int  # from clang; often 0,1,2,4,8, or 16
    KIND: ClassVar[str | None] = "Primitive"
    __json_field_order__: ClassVar[list[str] | None] = [
        "primitive_kind",
        "name",
        "is_signed",
        "size_bytes",
    ]


@dataclass
class Pointer(SerDeMixin):
    """
    T* or qualified T*.
    pointee=None means void* → emit OpaquePointer directly.
    """

    pointee: Type | None = field(
        metadata={
            "from_json": lambda raw: None if raw is None else type_from_json(raw),
        }
    )  # None == void*
    qualifiers: Qualifiers = field(default_factory=Qualifiers)
    KIND: ClassVar[str | None] = "Pointer"

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Pointer")
        pointee = d.get("pointee")
        return cls(
            pointee=None if pointee is None else type_from_json(pointee),
            qualifiers=Qualifiers.from_json_dict(
                d.get("qualifiers", {"is_const": d.get("is_const", False)})
            ),
        )


@dataclass
class Array(SerDeMixin):
    """
    Fixed-size, incomplete, flexible, or variable array.

    ``array_kind`` distinguishes the source construct so later phases do not
    need to infer whether ``size=None`` came from a flexible array member,
    incomplete array, or VLA-like construct.
    """

    element: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    size: int | None
    array_kind: ArrayKind = "fixed"
    KIND: ClassVar[str | None] = "Array"


@dataclass
class FunctionPtr(SerDeMixin):
    """
    Function pointer type: ret (*)(p0, p1, ...).
    Full ret/params are retained for documentation and future tooling.
    """

    ret: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    params: list[Type] = field(
        metadata={"from_json": lambda raw: [type_from_json(p) for p in raw]}
    )
    param_names: list[str] | None = None
    is_variadic: bool = False
    calling_convention: str | None = None
    is_noreturn: bool = False
    KIND: ClassVar[str | None] = "FunctionPtr"


@dataclass
class OpaqueRecordRef(SerDeMixin):
    """Reference to a declared-but-incomplete struct or union type.

    This node represents intentionally opaque record handles such as
    ``struct FILE`` or public forward-declared library types. It is distinct
    from :class:`UnsupportedType`, which means the parser saw a type it could
    not model faithfully.
    """

    decl_id: str = field(metadata={"json_missing": lambda d: d["name"]})
    name: str
    c_name: str = field(metadata={"json_missing": lambda d: d["name"]})
    is_union: bool = False
    KIND: ClassVar[str | None] = "OpaqueRecordRef"


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
    KIND: ClassVar[str | None] = "UnsupportedType"


@dataclass
class ComplexType(SerDeMixin):
    """C complex scalar modeled as two primitive lanes.

    The element primitive captures the ABI lane type, while ``size_bytes``
    preserves the exact layout width reported by clang.
    """

    element: Primitive
    size_bytes: int
    KIND: ClassVar[str | None] = "ComplexType"


@dataclass
class VectorType(SerDeMixin):
    """SIMD or compiler-extension vector type.

    This preserves extension vector shapes as structured IR instead of
    collapsing them into unsupported opaque blobs.
    """

    element: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    count: int | None
    size_bytes: int
    is_ext_vector: bool = False
    KIND: ClassVar[str | None] = "VectorType"


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

    decl_id: str = field(metadata={"json_missing": lambda d: d["name"]})
    name: str
    c_name: str
    is_union: bool = False
    size_bytes: int = 0
    is_anonymous: bool = False
    KIND: ClassVar[str | None] = "StructRef"


@dataclass(frozen=True)
class EnumRef(SerDeMixin):
    """Reference to a named enum declaration with its integer ABI type."""

    decl_id: str = field(metadata={"json_missing": lambda d: d["name"]})
    name: str
    c_name: str
    KIND: ClassVar[str | None] = "EnumRef"
    underlying: Primitive = field(
        metadata={"from_json": lambda raw: type_from_json(raw)}  # type: ignore[arg-type]
    )


@dataclass
class TypeRef(SerDeMixin):
    """
    A named reference to a C typedef where the typedef name appears in a type
    position (parameter, field, pointer target, etc.).

    ``canonical`` is the fully resolved :class:`Type` for ABI lowering; the
    typedef ``name`` preserves the C API spelling for readable emission.
    """

    decl_id: str = field(metadata={"json_missing": lambda d: d["name"]})
    name: str
    canonical: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    KIND: ClassVar[str | None] = "TypeRef"


# ─────────────────────────────────────────────
#  Decl — top-level declaration nodes
# ─────────────────────────────────────────────


@dataclass
class Field:
    """One member of a struct or union."""

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

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "source_name": self.source_name,
            "type": self.type.to_json_dict(),
            "byte_offset": self.byte_offset,
            "is_anonymous": self.is_anonymous,
        }
        if self.is_bitfield:
            out["is_bitfield"] = True
            out["bit_offset"] = self.bit_offset
            out["bit_width"] = self.bit_width
        return out

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            name=d["name"],
            source_name=d.get("source_name", d["name"]),
            type=type_from_json(d["type"]),
            byte_offset=d["byte_offset"],
            is_anonymous=d.get("is_anonymous", False),
            is_bitfield=d.get("is_bitfield", False),
            bit_offset=d.get("bit_offset", 0),
            bit_width=d.get("bit_width", 0),
        )


@dataclass
class Struct(SerDeMixin):
    """
    struct or union — always fully laid out.
    is_union=True means all fields share offset 0; size is the largest member.
    Fields are in declaration order (clang cursor order).
    """

    decl_id: str = field(metadata={"json_missing": lambda d: d["name"]})
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
    KIND: ClassVar[str | None] = "Struct"


# Recursive type nodes (no inline Struct/Bitfield — layouts are Struct decls + Field metadata)
Type = Union[
    Primitive,
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
    KIND: ClassVar[str | None] = "IntLiteral"


@dataclass(frozen=True)
class FloatLiteral(SerDeMixin):
    """Floating-point constant expression leaf, preserved as source text."""

    value: str
    KIND: ClassVar[str | None] = "FloatLiteral"


@dataclass(frozen=True)
class StringLiteral(SerDeMixin):
    """String-literal constant expression leaf without surrounding quotes."""

    value: str
    KIND: ClassVar[str | None] = "StringLiteral"


@dataclass(frozen=True)
class CharLiteral(SerDeMixin):
    """Character-literal constant expression leaf without surrounding quotes."""

    value: str
    KIND: ClassVar[str | None] = "CharLiteral"


@dataclass(frozen=True)
class NullPtrLiteral(SerDeMixin):
    """Null-pointer constant expression leaf."""

    KIND: ClassVar[str | None] = "NullPtrLiteral"


@dataclass(frozen=True)
class RefExpr(SerDeMixin):
    """Reference to another constant-like symbol in a constant expression."""

    name: str
    KIND: ClassVar[str | None] = "RefExpr"


@dataclass(frozen=True)
class UnaryExpr(SerDeMixin):
    """Unary constant expression such as ``-x`` or ``~x``."""

    op: str
    operand: ConstExpr = field(
        metadata={"from_json": lambda raw: const_expr_from_json(raw)}
    )
    KIND: ClassVar[str | None] = "UnaryExpr"
    __json_field_order__: ClassVar[list[str] | None] = ["op", "operand"]


@dataclass(frozen=True)
class BinaryExpr(SerDeMixin):
    """Binary constant expression such as ``a | b`` or ``x << 2``."""

    op: str
    lhs: ConstExpr = field(
        metadata={"from_json": lambda raw: const_expr_from_json(raw)}
    )
    rhs: ConstExpr = field(
        metadata={"from_json": lambda raw: const_expr_from_json(raw)}
    )
    KIND: ClassVar[str | None] = "BinaryExpr"


@dataclass(frozen=True)
class CastExpr(SerDeMixin):
    """Cast applied inside a constant expression."""

    target: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    expr: ConstExpr = field(
        metadata={"from_json": lambda raw: const_expr_from_json(raw)}
    )
    KIND: ClassVar[str | None] = "CastExpr"


@dataclass(frozen=True)
class SizeOfExpr(SerDeMixin):
    """``sizeof(T)`` constant expression."""

    target: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    KIND: ClassVar[str | None] = "SizeOfExpr"


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
    __json_field_order__: ClassVar[list[str] | None] = ["name", "c_name", "value"]


@dataclass
class Enum(SerDeMixin):
    """
    C enum.  Emitted as a thin struct:
        @fieldwise_init
        struct EnumName(Copyable, Movable, RegisterPassable):
            var value: <underlying Mojo int>
            comptime MEMBER = Self(<underlying>(value))
    underlying is always Primitive with kind INT (C enum base type is integer).
    """

    decl_id: str = field(metadata={"json_missing": lambda d: d["name"]})
    name: str
    c_name: str
    underlying: Primitive
    enumerants: list[Enumerant]
    KIND: ClassVar[str | None] = "Enum"


@dataclass
class Typedef(SerDeMixin):
    """
    typedef <type> <name>.

    ``aliased`` is the direct underlying type (one typedef step), often a
    :class:`TypeRef` when the underlying names another typedef.

    ``canonical`` is the fully unrolled type for ABI layout and for lowering
    inside compound positions (struct fields, function pointer signatures).
    """

    decl_id: str = field(metadata={"json_missing": lambda d: d["name"]})
    name: str
    aliased: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    canonical: Type = field(
        metadata={
            "from_json": lambda raw: type_from_json(raw),
            "json_missing": lambda d: d["aliased"],
        }
    )
    KIND: ClassVar[str | None] = "Typedef"


@dataclass
class Param(SerDeMixin):
    name: str  # "" for anonymous params
    type: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    KIND: ClassVar[str | None] = None
    __json_field_order__: ClassVar[list[str] | None] = ["name", "type"]


@dataclass
class Function(SerDeMixin):
    """
    Any top-level C function declaration.
    link_name is the actual symbol: may differ from name after NameMapper.
    is_variadic=True → emitted as a comment block, no body generated.
    """

    name: str  # Mojo-mapped name (post NameMapper)
    link_name: str  # original C symbol name (used in external_call)
    ret: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    params: list[Param]
    is_variadic: bool = False
    decl_id: str = field(default="", metadata={"json_missing": lambda d: d["name"]})
    calling_convention: str | None = None
    is_noreturn: bool = False
    KIND: ClassVar[str | None] = "Function"
    __json_field_order__: ClassVar[list[str] | None] = [
        "decl_id",
        "name",
        "link_name",
        "ret",
        "params",
        "is_variadic",
        "calling_convention",
        "is_noreturn",
    ]


@dataclass
class Const(SerDeMixin):
    """
    Top-level C constant or macro-like declaration with an unevaluated or partly
    evaluated constant expression.

    The ``type`` field is the best-effort declared or inferred type; ``expr``
    preserves the expression shape when full evaluation is not desirable.
    """

    name: str
    type: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    expr: ConstExpr = field(
        metadata={"from_json": lambda raw: const_expr_from_json(raw)}
    )
    KIND: ClassVar[str | None] = "Const"


@dataclass
class MacroDecl(SerDeMixin):
    """Top-level preprocessor macro preserved from the primary header.

    Macros are preserved even when their replacement list cannot be lowered to
    the supported :class:`ConstExpr` subset. ``tokens`` keeps the original
    replacement spelling, while ``expr`` and ``type`` are populated only for
    macros the parser can structurally understand today.
    """

    name: str
    tokens: list[str]
    kind: MacroDeclKind = field(metadata={"json_key": "macro_kind"})
    expr: ConstExpr | None = field(
        default=None,
        metadata={
            "from_json": lambda raw: None if raw is None else const_expr_from_json(raw),
        },
    )
    type: Type | None = field(
        default=None,
        metadata={
            "from_json": lambda raw: None if raw is None else type_from_json(raw)
        },
    )
    diagnostic: str | None = None
    KIND: ClassVar[str | None] = "MacroDecl"
    __json_field_order__: ClassVar[list[str] | None] = [
        "name",
        "tokens",
        "macro_kind",
        "expr",
        "type",
        "diagnostic",
    ]


@dataclass
class GlobalVar(SerDeMixin):
    """Top-level variable declaration exposed by the bound library.

    This covers exported globals and ``extern const`` declarations that should
    remain part of the binding surface even when they are not reducible to a
    compile-time constant.
    """

    decl_id: str = field(metadata={"json_missing": lambda d: d["name"]})
    name: str
    link_name: str
    type: Type = field(metadata={"from_json": lambda raw: type_from_json(raw)})
    is_const: bool = False
    initializer: ConstExpr | None = field(
        default=None,
        metadata={
            "from_json": lambda raw: None if raw is None else const_expr_from_json(raw),
        },
    )
    KIND: ClassVar[str | None] = "GlobalVar"


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
    __json_field_order__: ClassVar[list[str] | None] = [
        "severity",
        "message",
        "file",
        "line",
        "col",
        "decl_id",
    ]


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
    decls: list[Decl] = field(
        default_factory=list,
        metadata={"from_json": lambda raw: [decl_from_json(x) for x in raw]},
    )
    diagnostics: list[IRDiagnostic] = field(default_factory=list)
    KIND: ClassVar[str | None] = "Unit"

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize this unit to a JSON string (default: indented for readability)."""
        return json.dumps(self.to_json_dict(), indent=indent)


_TYPE_FROM_JSON: dict[str, Callable[[dict[str, Any]], Type]] = {
    "Primitive": Primitive.from_json_dict,
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

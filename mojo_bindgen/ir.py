# bindgen/ir/types.py
from __future__ import annotations
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Literal, Self, Union


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
"""Categories for types recognized by the parser but not fully modeled."""


ArrayKind = Literal["fixed", "incomplete", "flexible", "variable"]
"""Array-shape categories that matter for ABI-faithful lowering."""


MacroDeclKind = Literal[
    "object_like_supported",
    "object_like_unsupported",
    "function_like_unsupported",
    "empty",
    "predefined",
    "invalid",
]
"""Classification of preserved preprocessor macro declarations."""


@dataclass(frozen=True)
class Qualifiers:
    """C type qualifiers preserved on pointee types and other referenced types."""

    is_const: bool = False
    is_volatile: bool = False
    is_restrict: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "is_const": self.is_const,
            "is_volatile": self.is_volatile,
            "is_restrict": self.is_restrict,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            is_const=d.get("is_const", False),
            is_volatile=d.get("is_volatile", False),
            is_restrict=d.get("is_restrict", False),
        )


def _expect_kind(d: dict[str, Any], kind: str) -> None:
    if d.get("kind") != kind:
        raise ValueError(f"expected kind {kind!r}, got {d.get('kind')!r}")


# ─────────────────────────────────────────────
#  Type — recursive type tree
# ─────────────────────────────────────────────

@dataclass
class Primitive:
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
    name: str               # canonical C spelling: "unsigned int", "long long", ...
    kind: PrimitiveKind
    is_signed: bool
    size_bytes: int         # from clang; often 0,1,2,4,8, or 16

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Primitive",
            "primitive_kind": self.kind.value,
            "name": self.name,
            "is_signed": self.is_signed,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Primitive")
        return cls(
            name=d["name"],
            kind=PrimitiveKind(d["primitive_kind"]),
            is_signed=d["is_signed"],
            size_bytes=d["size_bytes"],
        )


@dataclass
class Pointer:
    """
    T* or qualified T*.
    pointee=None means void* → emit OpaquePointer directly.
    """
    pointee: Type | None  # None == void*
    qualifiers: Qualifiers = field(default_factory=Qualifiers)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Pointer",
            "pointee": None if self.pointee is None else self.pointee.to_json_dict(),
            "qualifiers": self.qualifiers.to_json_dict(),
        }

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
class Array:
    """
    Fixed-size, incomplete, flexible, or variable array.

    ``array_kind`` distinguishes the source construct so later phases do not
    need to infer whether ``size=None`` came from a flexible array member,
    incomplete array, or VLA-like construct.
    """
    element: Type
    size: int | None
    array_kind: ArrayKind = "fixed"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Array",
            "element": self.element.to_json_dict(),
            "size": self.size,
            "array_kind": self.array_kind,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Array")
        return cls(
            element=type_from_json(d["element"]),
            size=d.get("size"),
            array_kind=d.get("array_kind", "fixed"),
        )


@dataclass
class FunctionPtr:
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

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "FunctionPtr",
            "ret": self.ret.to_json_dict(),
            "params": [p.to_json_dict() for p in self.params],
            "param_names": self.param_names,
            "is_variadic": self.is_variadic,
            "calling_convention": self.calling_convention,
            "is_noreturn": self.is_noreturn,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "FunctionPtr")
        return cls(
            ret=type_from_json(d["ret"]),
            params=[type_from_json(p) for p in d["params"]],
            param_names=d.get("param_names"),
            is_variadic=d.get("is_variadic", False),
            calling_convention=d.get("calling_convention"),
            is_noreturn=d.get("is_noreturn", False),
        )


@dataclass
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

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "OpaqueRecordRef",
            "decl_id": self.decl_id,
            "name": self.name,
            "c_name": self.c_name,
            "is_union": self.is_union,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "OpaqueRecordRef")
        return cls(
            decl_id=d.get("decl_id", d["name"]),
            name=d["name"],
            c_name=d.get("c_name", d["name"]),
            is_union=d.get("is_union", False),
        )


@dataclass
class UnsupportedType:
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

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "UnsupportedType",
            "category": self.category,
            "spelling": self.spelling,
            "reason": self.reason,
            "size_bytes": self.size_bytes,
            "align_bytes": self.align_bytes,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "UnsupportedType")
        return cls(
            category=d["category"],
            spelling=d["spelling"],
            reason=d["reason"],
            size_bytes=d.get("size_bytes"),
            align_bytes=d.get("align_bytes"),
        )


@dataclass
class ComplexType:
    """C complex scalar modeled as two primitive lanes.

    The element primitive captures the ABI lane type, while ``size_bytes``
    preserves the exact layout width reported by clang.
    """

    element: Primitive
    size_bytes: int

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "ComplexType",
            "element": self.element.to_json_dict(),
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "ComplexType")
        return cls(
            element=type_from_json(d["element"]),  # type: ignore[arg-type]
            size_bytes=d["size_bytes"],
        )


@dataclass
class VectorType:
    """SIMD or compiler-extension vector type.

    This preserves extension vector shapes as structured IR instead of
    collapsing them into unsupported opaque blobs.
    """

    element: Type
    count: int | None
    size_bytes: int
    is_ext_vector: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "VectorType",
            "element": self.element.to_json_dict(),
            "count": self.count,
            "size_bytes": self.size_bytes,
            "is_ext_vector": self.is_ext_vector,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "VectorType")
        return cls(
            element=type_from_json(d["element"]),
            count=d.get("count"),
            size_bytes=d["size_bytes"],
            is_ext_vector=d.get("is_ext_vector", False),
        )


@dataclass(frozen=True)
class StructRef:
    """
    Reference to a struct or union layout by name.

    Full :class:`Struct` definitions live only on :class:`Unit` as declarations;
    field and parameter types use ``StructRef`` so :class:`Type` does not embed
    layouts. ``name`` and ``c_name`` are usually the same C tag; anonymous
    record bodies use a stable ``__bindgen_anon_<hash>`` synthetic name (see parser).

    Unions carry ``is_union=True`` and ``size_bytes`` so the emitter can lower
    by-value unions to ``InlineArray[UInt8, size]`` without a separate lookup.
    """
    decl_id: str
    name: str
    c_name: str
    is_union: bool = False
    size_bytes: int = 0
    is_anonymous: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "StructRef",
            "decl_id": self.decl_id,
            "name": self.name,
            "c_name": self.c_name,
            "is_union": self.is_union,
            "size_bytes": self.size_bytes,
            "is_anonymous": self.is_anonymous,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "StructRef")
        return cls(
            decl_id=d.get("decl_id", d["name"]),
            name=d["name"],
            c_name=d["c_name"],
            is_union=d.get("is_union", False),
            size_bytes=d.get("size_bytes", 0),
            is_anonymous=d.get("is_anonymous", False),
        )


@dataclass(frozen=True)
class EnumRef:
    """Reference to a named enum declaration with its integer ABI type."""

    decl_id: str
    name: str
    c_name: str
    underlying: Primitive

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "EnumRef",
            "decl_id": self.decl_id,
            "name": self.name,
            "c_name": self.c_name,
            "underlying": self.underlying.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "EnumRef")
        return cls(
            decl_id=d.get("decl_id", d["name"]),
            name=d["name"],
            c_name=d["c_name"],
            underlying=type_from_json(d["underlying"]),  # type: ignore[arg-type]
        )


@dataclass
class TypeRef:
    """
    A named reference to a C typedef where the typedef name appears in a type
    position (parameter, field, pointer target, etc.).

    ``canonical`` is the fully resolved :class:`Type` for ABI lowering; the
    typedef ``name`` preserves the C API spelling for readable emission.
    """

    decl_id: str
    name: str
    canonical: Type

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "TypeRef",
            "decl_id": self.decl_id,
            "name": self.name,
            "canonical": self.canonical.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "TypeRef")
        return cls(
            decl_id=d.get("decl_id", d["name"]),
            name=d["name"],
            canonical=type_from_json(d["canonical"]),
        )


# ─────────────────────────────────────────────
#  Decl — top-level declaration nodes
# ─────────────────────────────────────────────

@dataclass
class Param:
    name: str           # "" for anonymous params
    type: Type

    def to_json_dict(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type.to_json_dict()}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        return cls(name=d["name"], type=type_from_json(d["type"]))


@dataclass
class Function:
    """
    Any top-level C function declaration.
    link_name is the actual symbol: may differ from name after NameMapper.
    is_variadic=True → emitted as a comment block, no body generated.
    """
    name: str           # Mojo-mapped name (post NameMapper)
    link_name: str      # original C symbol name (used in external_call)
    ret: Type
    params: list[Param]
    is_variadic: bool = False
    decl_id: str = ""
    calling_convention: str | None = None
    is_noreturn: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Function",
            "decl_id": self.decl_id,
            "name": self.name,
            "link_name": self.link_name,
            "ret": self.ret.to_json_dict(),
            "params": [p.to_json_dict() for p in self.params],
            "is_variadic": self.is_variadic,
            "calling_convention": self.calling_convention,
            "is_noreturn": self.is_noreturn,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Function")
        return cls(
            decl_id=d.get("decl_id", d["name"]),
            name=d["name"],
            link_name=d["link_name"],
            ret=type_from_json(d["ret"]),
            params=[Param.from_json_dict(p) for p in d["params"]],
            is_variadic=d.get("is_variadic", False),
            calling_convention=d.get("calling_convention"),
            is_noreturn=d.get("is_noreturn", False),
        )


@dataclass
class Field:
    """One member of a struct or union."""
    name: str
    source_name: str
    type: Type
    byte_offset: int    # from clang Type.get_offset(field_name) // 8
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
class Struct:
    """
    struct or union — always fully laid out.
    is_union=True means all fields share offset 0; size is the largest member.
    Fields are in declaration order (clang cursor order).
    """
    decl_id: str
    name: str           # Mojo name
    c_name: str         # original C name for cross-reference
    fields: list[Field]
    size_bytes: int
    align_bytes: int
    is_union: bool = False
    is_anonymous: bool = False
    is_complete: bool = True
    is_packed: bool = False
    requested_align_bytes: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Struct",
            "decl_id": self.decl_id,
            "name": self.name,
            "c_name": self.c_name,
            "fields": [f.to_json_dict() for f in self.fields],
            "size_bytes": self.size_bytes,
            "align_bytes": self.align_bytes,
            "is_union": self.is_union,
            "is_anonymous": self.is_anonymous,
            "is_complete": self.is_complete,
            "is_packed": self.is_packed,
            "requested_align_bytes": self.requested_align_bytes,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Struct")
        return cls(
            decl_id=d.get("decl_id", d["name"]),
            name=d["name"],
            c_name=d["c_name"],
            fields=[Field.from_json_dict(f) for f in d["fields"]],
            size_bytes=d["size_bytes"],
            align_bytes=d["align_bytes"],
            is_union=d.get("is_union", False),
            is_anonymous=d.get("is_anonymous", False),
            is_complete=d.get("is_complete", True),
            is_packed=d.get("is_packed", False),
            requested_align_bytes=d.get("requested_align_bytes"),
        )


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
class IntLiteral:
    """Integer constant expression leaf."""

    value: int

    def to_json_dict(self) -> dict[str, Any]:
        return {"kind": "IntLiteral", "value": self.value}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "IntLiteral")
        return cls(value=d["value"])


@dataclass(frozen=True)
class FloatLiteral:
    """Floating-point constant expression leaf, preserved as source text."""

    value: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"kind": "FloatLiteral", "value": self.value}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "FloatLiteral")
        return cls(value=d["value"])


@dataclass(frozen=True)
class StringLiteral:
    """String-literal constant expression leaf without surrounding quotes."""

    value: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"kind": "StringLiteral", "value": self.value}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "StringLiteral")
        return cls(value=d["value"])


@dataclass(frozen=True)
class CharLiteral:
    """Character-literal constant expression leaf without surrounding quotes."""

    value: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"kind": "CharLiteral", "value": self.value}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "CharLiteral")
        return cls(value=d["value"])


@dataclass(frozen=True)
class NullPtrLiteral:
    """Null-pointer constant expression leaf."""

    def to_json_dict(self) -> dict[str, Any]:
        return {"kind": "NullPtrLiteral"}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "NullPtrLiteral")
        return cls()


@dataclass(frozen=True)
class RefExpr:
    """Reference to another constant-like symbol in a constant expression."""

    name: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"kind": "RefExpr", "name": self.name}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "RefExpr")
        return cls(name=d["name"])


@dataclass(frozen=True)
class UnaryExpr:
    """Unary constant expression such as ``-x`` or ``~x``."""

    op: str
    operand: ConstExpr

    def to_json_dict(self) -> dict[str, Any]:
        return {"kind": "UnaryExpr", "op": self.op, "operand": self.operand.to_json_dict()}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "UnaryExpr")
        return cls(op=d["op"], operand=const_expr_from_json(d["operand"]))


@dataclass(frozen=True)
class BinaryExpr:
    """Binary constant expression such as ``a | b`` or ``x << 2``."""

    op: str
    lhs: ConstExpr
    rhs: ConstExpr

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "BinaryExpr",
            "op": self.op,
            "lhs": self.lhs.to_json_dict(),
            "rhs": self.rhs.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "BinaryExpr")
        return cls(
            op=d["op"],
            lhs=const_expr_from_json(d["lhs"]),
            rhs=const_expr_from_json(d["rhs"]),
        )


@dataclass(frozen=True)
class CastExpr:
    """Cast applied inside a constant expression."""

    target: Type
    expr: ConstExpr

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "CastExpr",
            "target": self.target.to_json_dict(),
            "expr": self.expr.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "CastExpr")
        return cls(
            target=type_from_json(d["target"]),
            expr=const_expr_from_json(d["expr"]),
        )


@dataclass(frozen=True)
class SizeOfExpr:
    """``sizeof(T)`` constant expression."""

    target: Type

    def to_json_dict(self) -> dict[str, Any]:
        return {"kind": "SizeOfExpr", "target": self.target.to_json_dict()}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "SizeOfExpr")
        return cls(target=type_from_json(d["target"]))


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
"""Structured constant-expression subset used by macros, enums, and globals."""

@dataclass
class Enumerant:
    name: str           # Mojo-mapped constant name
    c_name: str         # original C name
    value: int

    def to_json_dict(self) -> dict[str, Any]:
        return {"name": self.name, "c_name": self.c_name, "value": self.value}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        return cls(name=d["name"], c_name=d["c_name"], value=d["value"])


@dataclass
class Enum:
    """
    C enum.  Emitted as a thin struct:
        @fieldwise_init
        struct EnumName(Copyable, Movable, RegisterPassable):
            var value: <underlying Mojo int>
            comptime MEMBER = Self(<underlying>(value))
    underlying is always Primitive with kind INT (C enum base type is integer).
    """
    decl_id: str
    name: str
    c_name: str
    underlying: Primitive
    enumerants: list[Enumerant]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Enum",
            "decl_id": self.decl_id,
            "name": self.name,
            "c_name": self.c_name,
            "underlying": self.underlying.to_json_dict(),
            "enumerants": [x.to_json_dict() for x in self.enumerants],
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Enum")
        return cls(
            decl_id=d.get("decl_id", d["name"]),
            name=d["name"],
            c_name=d["c_name"],
            underlying=type_from_json(d["underlying"]),  # type: ignore[arg-type]
            enumerants=[Enumerant.from_json_dict(x) for x in d["enumerants"]],
        )


@dataclass
class Typedef:
    """
    typedef <type> <name>.

    ``aliased`` is the direct underlying type (one typedef step), often a
    :class:`TypeRef` when the underlying names another typedef.

    ``canonical`` is the fully unrolled type for ABI layout and for lowering
    inside compound positions (struct fields, function pointer signatures).
    """
    decl_id: str
    name: str
    aliased: Type
    canonical: Type

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Typedef",
            "decl_id": self.decl_id,
            "name": self.name,
            "aliased": self.aliased.to_json_dict(),
            "canonical": self.canonical.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Typedef")
        aliased = type_from_json(d["aliased"])
        canonical = type_from_json(d["canonical"]) if "canonical" in d else aliased
        return cls(
            decl_id=d.get("decl_id", d["name"]),
            name=d["name"],
            aliased=aliased,
            canonical=canonical,
        )


@dataclass
class Const:
    """
    Top-level C constant or macro-like declaration with an unevaluated or partly
    evaluated constant expression.

    The ``type`` field is the best-effort declared or inferred type; ``expr``
    preserves the expression shape when full evaluation is not desirable.
    """
    name: str
    type: Type
    expr: ConstExpr

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Const",
            "name": self.name,
            "type": self.type.to_json_dict(),
            "expr": self.expr.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Const")
        return cls(
            name=d["name"],
            type=type_from_json(d["type"]),
            expr=const_expr_from_json(d["expr"]),
        )


@dataclass
class MacroDecl:
    """Top-level preprocessor macro preserved from the primary header.

    Macros are preserved even when their replacement list cannot be lowered to
    the supported :class:`ConstExpr` subset. ``tokens`` keeps the original
    replacement spelling, while ``expr`` and ``type`` are populated only for
    macros the parser can structurally understand today.
    """

    name: str
    tokens: list[str]
    kind: MacroDeclKind
    expr: ConstExpr | None = None
    type: Type | None = None
    diagnostic: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "MacroDecl",
            "name": self.name,
            "tokens": self.tokens,
            "macro_kind": self.kind,
            "expr": None if self.expr is None else self.expr.to_json_dict(),
            "type": None if self.type is None else self.type.to_json_dict(),
            "diagnostic": self.diagnostic,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "MacroDecl")
        expr = d.get("expr")
        ty = d.get("type")
        return cls(
            name=d["name"],
            tokens=list(d.get("tokens", [])),
            kind=d["macro_kind"],
            expr=None if expr is None else const_expr_from_json(expr),
            type=None if ty is None else type_from_json(ty),
            diagnostic=d.get("diagnostic"),
        )


@dataclass
class GlobalVar:
    """Top-level variable declaration exposed by the bound library.

    This covers exported globals and ``extern const`` declarations that should
    remain part of the binding surface even when they are not reducible to a
    compile-time constant.
    """

    decl_id: str
    name: str
    link_name: str
    type: Type
    is_const: bool = False
    initializer: ConstExpr | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "GlobalVar",
            "decl_id": self.decl_id,
            "name": self.name,
            "link_name": self.link_name,
            "type": self.type.to_json_dict(),
            "is_const": self.is_const,
            "initializer": None if self.initializer is None else self.initializer.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "GlobalVar")
        init = d.get("initializer")
        return cls(
            decl_id=d.get("decl_id", d["name"]),
            name=d["name"],
            link_name=d["link_name"],
            type=type_from_json(d["type"]),
            is_const=d.get("is_const", False),
            initializer=None if init is None else const_expr_from_json(init),
        )


@dataclass(frozen=True)
class IRDiagnostic:
    """Parser-side note about a recognized construct that cannot be modeled fully."""

    severity: str
    message: str
    file: str | None = None
    line: int | None = None
    col: int | None = None
    decl_id: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "decl_id": self.decl_id,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            severity=d["severity"],
            message=d["message"],
            file=d.get("file"),
            line=d.get("line"),
            col=d.get("col"),
            decl_id=d.get("decl_id"),
        )


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
class Unit:
    """One parsed header translation unit plus its declarations and diagnostics."""

    source_header: str
    library: str            # e.g. "zlib"
    link_name: str          # e.g. "z"  (used in DLHandle)
    decls: list[Decl] = field(default_factory=list)
    diagnostics: list[IRDiagnostic] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Unit",
            "source_header": self.source_header,
            "library": self.library,
            "link_name": self.link_name,
            "decls": [d.to_json_dict() for d in self.decls],
            "diagnostics": [d.to_json_dict() for d in self.diagnostics],
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> Self:
        _expect_kind(data, "Unit")
        return cls(
            source_header=data["source_header"],
            library=data["library"],
            link_name=data["link_name"],
            decls=[decl_from_json(x) for x in data["decls"]],
            diagnostics=[IRDiagnostic.from_json_dict(x) for x in data.get("diagnostics", [])],
        )

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

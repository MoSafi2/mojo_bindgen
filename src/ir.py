# bindgen/ir/types.py
from __future__ import annotations
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Self, Union


class PrimitiveKind(StrEnum):
    """Discriminant for C scalars; JSON-serializes to the enum value string."""

    INT = "INT"
    CHAR = "CHAR"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    VOID = "VOID"


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
    T* or const T*.
    pointee=None means void* → emit OpaquePointer directly.
    """
    pointee: Type | None  # None == void*
    is_const: bool = False  # const T* (read-only pointee)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Pointer",
            "pointee": None if self.pointee is None else self.pointee.to_json_dict(),
            "is_const": self.is_const,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Pointer")
        pointee = d.get("pointee")
        return cls(
            pointee=None if pointee is None else type_from_json(pointee),
            is_const=d["is_const"],
        )


@dataclass
class Array:
    """
    Fixed-size array T[N] → InlineArray[T, N].
    If size is None the original C was T[] or T* decay — emit UnsafePointer[T].
    """
    element: Type
    size: int | None        # None for unsized / pointer-decay

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Array",
            "element": self.element.to_json_dict(),
            "size": self.size,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Array")
        return cls(
            element=type_from_json(d["element"]),
            size=d.get("size"),
        )


@dataclass
class FunctionPtr:
    """
    Function pointer type: ret (*)(p0, p1, ...).
    Full ret/params are retained for documentation and future tooling.
    """
    ret: Type
    params: list[Type]
    is_variadic: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "FunctionPtr",
            "ret": self.ret.to_json_dict(),
            "params": [p.to_json_dict() for p in self.params],
            "is_variadic": self.is_variadic,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "FunctionPtr")
        return cls(
            ret=type_from_json(d["ret"]),
            params=[type_from_json(p) for p in d["params"]],
            is_variadic=d.get("is_variadic", False),
        )


@dataclass
class Opaque:
    """
    A struct/union type that was declared but never defined in this translation unit.
    e.g.  struct FILE;   typedef struct _IO_FILE FILE;
    Emitted as:  alias FILE = OpaquePointer
    """
    name: str   # C name of the incomplete type

    def to_json_dict(self) -> dict[str, Any]:
        return {"kind": "Opaque", "name": self.name}

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Opaque")
        return cls(name=d["name"])


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
    name: str
    c_name: str
    is_union: bool = False
    size_bytes: int = 0

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "StructRef",
            "name": self.name,
            "c_name": self.c_name,
            "is_union": self.is_union,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "StructRef")
        return cls(
            name=d["name"],
            c_name=d["c_name"],
            is_union=d.get("is_union", False),
            size_bytes=d.get("size_bytes", 0),
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

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Function",
            "name": self.name,
            "link_name": self.link_name,
            "ret": self.ret.to_json_dict(),
            "params": [p.to_json_dict() for p in self.params],
            "is_variadic": self.is_variadic,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Function")
        return cls(
            name=d["name"],
            link_name=d["link_name"],
            ret=type_from_json(d["ret"]),
            params=[Param.from_json_dict(p) for p in d["params"]],
            is_variadic=d.get("is_variadic", False),
        )


@dataclass
class Field:
    """One member of a struct or union."""
    name: str
    type: Type
    byte_offset: int    # from clang Type.get_offset(field_name) // 8
    is_bitfield: bool = False
    """If True, ``type`` is the backing integer :class:`Primitive` only."""
    bit_offset: int = 0
    """Bit offset within the storage unit (from clang). Meaningful if ``is_bitfield``."""
    bit_width: int = 0
    """Width in bits. Meaningful if ``is_bitfield``."""

    def to_json_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "type": self.type.to_json_dict(),
            "byte_offset": self.byte_offset,
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
            type=type_from_json(d["type"]),
            byte_offset=d["byte_offset"],
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
    name: str           # Mojo name
    c_name: str         # original C name for cross-reference
    fields: list[Field]
    size_bytes: int
    align_bytes: int
    is_union: bool = False

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Struct",
            "name": self.name,
            "c_name": self.c_name,
            "fields": [f.to_json_dict() for f in self.fields],
            "size_bytes": self.size_bytes,
            "align_bytes": self.align_bytes,
            "is_union": self.is_union,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Struct")
        return cls(
            name=d["name"],
            c_name=d["c_name"],
            fields=[Field.from_json_dict(f) for f in d["fields"]],
            size_bytes=d["size_bytes"],
            align_bytes=d["align_bytes"],
            is_union=d.get("is_union", False),
        )


# Recursive type nodes (no inline Struct/Bitfield — layouts are Struct decls + Field metadata)
Type = Union[
    Primitive,
    Pointer,
    Array,
    FunctionPtr,
    Opaque,
    StructRef,
]

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
    C enum.  Emitted as:
        alias EnumName = UnderlyingMojoType
        alias MEMBER   = EnumName(value)
    underlying is always Primitive with kind INT (C enum base type is integer).
    """
    name: str
    c_name: str
    underlying: Primitive
    enumerants: list[Enumerant]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Enum",
            "name": self.name,
            "c_name": self.c_name,
            "underlying": self.underlying.to_json_dict(),
            "enumerants": [x.to_json_dict() for x in self.enumerants],
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Enum")
        return cls(
            name=d["name"],
            c_name=d["c_name"],
            underlying=type_from_json(d["underlying"]),  # type: ignore[arg-type]
            enumerants=[Enumerant.from_json_dict(x) for x in d["enumerants"]],
        )


@dataclass
class Typedef:
    """
    typedef <type> <name>.
    aliased is the fully resolved Type after TypeResolver unrolls chains.
    """
    name: str
    aliased: Type

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Typedef",
            "name": self.name,
            "aliased": self.aliased.to_json_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Typedef")
        return cls(name=d["name"], aliased=type_from_json(d["aliased"]))


@dataclass
class Const:
    """
    Integer or hex #define macros only.
    type is always Primitive.  value is a Python int.
    Emitted as:  alias NAME = MojoType(value)
    """
    name: str
    type: Primitive
    value: int          # Python int, handles hex fine

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Const",
            "name": self.name,
            "type": self.type.to_json_dict(),
            "value": self.value,
        }

    @classmethod
    def from_json_dict(cls, d: dict[str, Any]) -> Self:
        _expect_kind(d, "Const")
        return cls(
            name=d["name"],
            type=type_from_json(d["type"]),  # type: ignore[arg-type]
            value=d["value"],
        )


Decl = Union[
    Function,
    Struct,
    Enum,
    Typedef,
    Const,
]


@dataclass
class Unit:
    source_header: str
    library: str            # e.g. "zlib"
    link_name: str          # e.g. "z"  (used in DLHandle)
    decls: list[Decl] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "Unit",
            "source_header": self.source_header,
            "library": self.library,
            "link_name": self.link_name,
            "decls": [d.to_json_dict() for d in self.decls],
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> Self:
        _expect_kind(data, "Unit")
        return cls(
            source_header=data["source_header"],
            library=data["library"],
            link_name=data["link_name"],
            decls=[decl_from_json(x) for x in data["decls"]],
        )

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize this unit to a JSON string (default: indented for readability)."""
        return json.dumps(self.to_json_dict(), indent=indent)


_TYPE_FROM_JSON: dict[str, Callable[[dict[str, Any]], Type]] = {
    "Primitive": Primitive.from_json_dict,
    "Pointer": Pointer.from_json_dict,
    "Array": Array.from_json_dict,
    "FunctionPtr": FunctionPtr.from_json_dict,
    "Opaque": Opaque.from_json_dict,
    "StructRef": StructRef.from_json_dict,
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


_DECL_FROM_JSON: dict[str, Callable[[dict[str, Any]], Decl]] = {
    "Function": Function.from_json_dict,
    "Struct": Struct.from_json_dict,
    "Enum": Enum.from_json_dict,
    "Typedef": Typedef.from_json_dict,
    "Const": Const.from_json_dict,
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

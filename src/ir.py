# bindgen/ir/types.py
from __future__ import annotations
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Union


class PrimitiveKind(StrEnum):
    """Discriminant for C scalars; JSON-serializes to the enum value string."""

    INT = "INT"
    CHAR = "CHAR"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    VOID = "VOID"


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


@dataclass(frozen=True)
class BuiltinPrimitiveSpelling:
    """
    Kind (and for INT, signedness) for a canonical C/clang type spelling.
    Byte width is never stored here — it always comes from clang Type.get_size().
    """

    kind: PrimitiveKind
    is_signed: bool = False  # only used when kind is INT; ignored for CHAR (from clang)


@dataclass
class Pointer:
    """
    T* or const T*.
    pointee=None means void* → emit OpaquePointer directly.
    """
    pointee: Type | None  # None == void*
    is_const: bool = False  # const T* (read-only pointee)

@dataclass
class Array:
    """
    Fixed-size array T[N] → InlineArray[T, N].
    If size is None the original C was T[] or T* decay — emit UnsafePointer[T].
    """
    element: Type
    size: int | None        # None for unsized / pointer-decay

@dataclass
class FunctionPtr:
    """
    Function pointer type: ret (*)(p0, p1, ...).
    These cannot be called through Mojo's @external_call directly,
    so we always emit OpaquePointer + a comment showing the original signature.
    The full ret/params are retained in the IR for documentation and future tooling.
    """
    ret: Type
    params: list[Type]
    is_variadic: bool = False

@dataclass
class Opaque:
    """
    A struct/union type that was declared but never defined in this translation unit.
    e.g.  struct FILE;   typedef struct _IO_FILE FILE;
    Emitted as:  alias FILE = OpaquePointer
    """
    name: str   # C name of the incomplete type

@dataclass
class Bitfield:
    """
    A struct member declared as  uint32_t flags : 4.
    The backing_type is the declared integer type.
    bit_offset and bit_width come from clang Type.get_offset() / cursor.get_bit_field_width().
    Mojo has no bitfield syntax — we emit the full backing_type and annotate with a comment.
    """
    backing_type: Primitive
    bit_offset: int
    bit_width: int

# ─────────────────────────────────────────────
#  Decl — top-level declaration nodes
# ─────────────────────────────────────────────

@dataclass
class Param:
    name: str           # "" for anonymous params
    type: Type

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

@dataclass
class Field:
    """One member of a struct or union."""
    name: str
    type: Type
    byte_offset: int    # from clang Type.get_offset(field_name) // 8
    # If type is Bitfield, bit_offset/bit_width live inside it.

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

# Union of all valid type nodes (Struct included for nested layouts and parser cache)
Type = Union[
    Primitive,
    Pointer,
    Array,
    FunctionPtr,
    Opaque,
    Bitfield,
    Struct,
]

@dataclass
class Enumerant:
    name: str           # Mojo-mapped constant name
    c_name: str         # original C name
    value: int

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

@dataclass
class Typedef:
    """
    typedef <type> <name>.
    aliased is the fully resolved Type after TypeResolver unrolls chains.
    If aliased resolves to a Struct/Enum with the same name, skip emission
    (the struct/enum declaration already creates the name in Mojo scope).
    """
    name: str
    aliased: Type

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

Decl = Union[
    Function,
    Struct,
    Enum,
    Typedef,
    Const,
]

def _primitive_to_json(p: Primitive) -> dict[str, Any]:
    return {
        "kind": "Primitive",
        "primitive_kind": p.kind.value,
        "name": p.name,
        "is_signed": p.is_signed,
        "size_bytes": p.size_bytes,
    }


def type_to_json(t: Type) -> dict[str, Any]:
    """Serialize a Type node to a JSON-compatible dict (includes a ``kind`` tag)."""
    if isinstance(t, Primitive):
        return _primitive_to_json(t)
    if isinstance(t, Pointer):
        return {
            "kind": "Pointer",
            "pointee": None if t.pointee is None else type_to_json(t.pointee),
            "is_const": t.is_const,
        }
    if isinstance(t, Array):
        return {
            "kind": "Array",
            "element": type_to_json(t.element),
            "size": t.size,
        }
    if isinstance(t, FunctionPtr):
        return {
            "kind": "FunctionPtr",
            "ret": type_to_json(t.ret),
            "params": [type_to_json(p) for p in t.params],
            "is_variadic": t.is_variadic,
        }
    if isinstance(t, Opaque):
        return {"kind": "Opaque", "name": t.name}
    if isinstance(t, Bitfield):
        return {
            "kind": "Bitfield",
            "backing_type": _primitive_to_json(t.backing_type),
            "bit_offset": t.bit_offset,
            "bit_width": t.bit_width,
        }
    if isinstance(t, Struct):
        return {
            "kind": "Struct",
            "name": t.name,
            "c_name": t.c_name,
            "fields": [field_to_json(f) for f in t.fields],
            "size_bytes": t.size_bytes,
            "align_bytes": t.align_bytes,
            "is_union": t.is_union,
        }
    raise TypeError(f"unsupported Type variant: {type(t)!r}")


def field_to_json(f: Field) -> dict[str, Any]:
    return {
        "name": f.name,
        "type": type_to_json(f.type),
        "byte_offset": f.byte_offset,
    }


def param_to_json(p: Param) -> dict[str, Any]:
    return {"name": p.name, "type": type_to_json(p.type)}


def enumerant_to_json(e: Enumerant) -> dict[str, Any]:
    return {"name": e.name, "c_name": e.c_name, "value": e.value}


def decl_to_json(d: Decl) -> dict[str, Any]:
    if isinstance(d, Function):
        return {
            "kind": "Function",
            "name": d.name,
            "link_name": d.link_name,
            "ret": type_to_json(d.ret),
            "params": [param_to_json(p) for p in d.params],
            "is_variadic": d.is_variadic,
        }
    if isinstance(d, Struct):
        return {
            "kind": "Struct",
            "name": d.name,
            "c_name": d.c_name,
            "fields": [field_to_json(f) for f in d.fields],
            "size_bytes": d.size_bytes,
            "align_bytes": d.align_bytes,
            "is_union": d.is_union,
        }
    if isinstance(d, Enum):
        return {
            "kind": "Enum",
            "name": d.name,
            "c_name": d.c_name,
            "underlying": _primitive_to_json(d.underlying),
            "enumerants": [enumerant_to_json(x) for x in d.enumerants],
        }
    if isinstance(d, Typedef):
        return {
            "kind": "Typedef",
            "name": d.name,
            "aliased": type_to_json(d.aliased),
        }
    if isinstance(d, Const):
        return {
            "kind": "Const",
            "name": d.name,
            "type": _primitive_to_json(d.type),
            "value": d.value,
        }
    raise TypeError(f"unsupported Decl variant: {type(d)!r}")


def unit_to_json_dict(unit: Unit) -> dict[str, Any]:
    """Serialize a Unit to a JSON-compatible dict (tree structure, ``kind`` on unions)."""
    return {
        "kind": "Unit",
        "source_header": unit.source_header,
        "library": unit.library,
        "link_name": unit.link_name,
        "decls": [decl_to_json(d) for d in unit.decls],
    }


@dataclass
class Unit:
    source_header: str
    library: str            # e.g. "zlib"
    link_name: str          # e.g. "z"  (used in DLHandle)
    decls: list[Decl] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return unit_to_json_dict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize this unit to a JSON string (default: indented for readability)."""
        return json.dumps(self.to_json_dict(), indent=indent)
# bindgen/ir/types.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Union

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
    is_signed distinguishes int (True) from unsigned int (False).
    """
    name: str           # canonical C spelling: "unsigned int", "long long", ...
    is_signed: bool
    size_bytes: int     # from clang; often 0,1,2,4,8, or 16
    is_float: bool = False
    is_bool: bool = False
    is_void: bool = False   # the bare `void` type (not void*)


@dataclass(frozen=True)
class BuiltinPrimitiveSpelling:
    """
    Flags for a canonical C/clang type spelling used when building Primitive.
    Byte width is never stored here — it always comes from clang Type.get_size().
    """

    is_signed: bool = False
    is_float: bool = False
    is_bool: bool = False
    is_void: bool = False


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
    underlying is always a Primitive integer type.
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

@dataclass
class Unit:
    source_header: str
    library: str            # e.g. "zlib"
    link_name: str          # e.g. "z"  (used in DLHandle)
    decls: list[Decl] = field(default_factory=list)
"""Minimal Mojo-centric IR for post-CIR lowering and Mojo code generation.

This module intentionally models emitted Mojo declaration forms rather than
mirroring the C-facing declaration taxonomy from :mod:`mojo_bindgen.ir`.
It reuses CIR constant-expression nodes directly for comptime values.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Union

from mojo_bindgen.ir import ConstExpr, FloatKind, IntKind, const_expr_from_json
from mojo_bindgen.serde import SerdeFieldSpec, SerDeMixin, SerdeSpec


class StructKind(StrEnum):
    PLAIN = "plain"
    ENUM = "enum"
    OPAQUE = "opaque"


class AliasKind(StrEnum):
    TYPE_ALIAS = "type_alias"
    CALLBACK_SIGNATURE = "callback_signature"
    UNION_LAYOUT = "union_layout"
    CONST_VALUE = "const_value"
    MACRO_VALUE = "macro_value"


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


class MojoBuiltin(StrEnum):
    NONE = "NoneType"
    BOOL = "Bool"
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


FIXED_WIDTH_INT_BUILTINS: dict[tuple[bool, int], MojoBuiltin] = {
    (True, 1): MojoBuiltin.C_CHAR,
    (True, 2): MojoBuiltin.C_SHORT,
    (True, 4): MojoBuiltin.C_INT,
    (True, 8): MojoBuiltin.C_LONG_LONG,
    (True, 16): MojoBuiltin.INT128,
    (False, 1): MojoBuiltin.C_UCHAR,
    (False, 2): MojoBuiltin.C_USHORT,
    (False, 4): MojoBuiltin.C_UINT,
    (False, 8): MojoBuiltin.C_ULONG_LONG,
    (False, 16): MojoBuiltin.UINT128,
}


STD_FFI_INT_BUILTINS: dict[IntKind, MojoBuiltin] = {
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
}


FIXED_WIDTH_FLOAT_BUILTINS: dict[FloatKind, MojoBuiltin] = {
    FloatKind.FLOAT16: MojoBuiltin.FLOAT16,
    FloatKind.FLOAT: MojoBuiltin.C_FLOAT,
    FloatKind.DOUBLE: MojoBuiltin.C_DOUBLE,
}


STD_FFI_FLOAT_BUILTINS: dict[FloatKind, MojoBuiltin] = {
    FloatKind.FLOAT16: MojoBuiltin.FLOAT16,
    FloatKind.FLOAT: MojoBuiltin.C_FLOAT,
    FloatKind.DOUBLE: MojoBuiltin.C_DOUBLE,
}


@dataclass(frozen=True)
class LoweringNote(SerDeMixin):
    severity: LoweringSeverity
    message: str
    category: str


@dataclass
class ModuleCapabilities(SerDeMixin):
    needs_opaque_pointer_types: bool = False
    needs_atomic: bool = False
    needs_simd: bool = False
    needs_complex: bool = False
    needs_unsafe_union: bool = False
    needs_dl_handle_helpers: bool = False
    needs_global_helpers: bool = False
    ffi_scalar_imports: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BuiltinType(SerDeMixin):
    name: MojoBuiltin

    @property
    def text(self) -> str:
        return self.name.value


@dataclass(frozen=True)
class NamedType(SerDeMixin):
    name: str


@dataclass
class PointerType(SerDeMixin):
    pointee: MojoType | None
    mutability: PointerMutability
    origin: PointerOrigin


@dataclass(frozen=True)
class ArrayType(SerDeMixin):
    element: MojoType
    count: int


@dataclass
class ParametricType(SerDeMixin):
    base: str
    args: list[str] = field(default_factory=list)


@dataclass
class FunctionType(SerDeMixin):
    params: list[MojoType] = field(default_factory=list)
    ret: MojoType = field(default_factory=lambda: BuiltinType(MojoBuiltin.NONE))
    abi: str = "C"
    thin: bool = True


MojoType = Union[
    BuiltinType,
    NamedType,
    PointerType,
    ArrayType,
    ParametricType,
    FunctionType,
]


@dataclass(frozen=True)
class StoredMember(SerDeMixin):
    name: str
    type: MojoType
    byte_offset: int


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
    name: str
    logical_type: MojoType
    bit_offset: int
    bit_width: int
    signed: bool
    bool_semantics: bool = False


@dataclass
class BitfieldGroupMember(SerDeMixin):
    storage_name: str
    storage_type: MojoType
    byte_offset: int
    fields: list[BitfieldField] = field(default_factory=list)


StructMember = Union[
    StoredMember,
    PaddingMember,
    OpaqueStorageMember,
    BitfieldGroupMember,
]


@dataclass(frozen=True)
class EnumMember(SerDeMixin):
    name: str
    value: int


@dataclass(frozen=True)
class InitializerParam(SerDeMixin):
    name: str
    type: MojoType


@dataclass
class Initializer(SerDeMixin):
    params: list[InitializerParam] = field(default_factory=list)


@dataclass
class StructDecl(SerDeMixin):
    SERDE = SerdeSpec(fields={"kind": SerdeFieldSpec(json_key="struct_kind")})

    name: str
    traits: list[str] = field(default_factory=list)
    align: int | None = None
    fieldwise_init: bool = False
    kind: StructKind = StructKind.PLAIN
    members: list[StructMember] = field(default_factory=list)
    enum_members: list[EnumMember] = field(default_factory=list)
    initializers: list[Initializer] = field(default_factory=list)
    diagnostics: list[LoweringNote] = field(default_factory=list)


@dataclass
class AliasDecl(SerDeMixin):
    SERDE = SerdeSpec(fields={"kind": SerdeFieldSpec(json_key="alias_kind")})

    name: str
    kind: AliasKind
    type_value: MojoType | None = None
    const_value: ConstExpr | None = None
    diagnostics: list[LoweringNote] = field(default_factory=list)

    def has_payload(self) -> bool:
        return self.type_value is not None or self.const_value is not None

    def has_type_payload(self) -> bool:
        return self.type_value is not None and self.const_value is None

    def has_const_payload(self) -> bool:
        return self.const_value is not None and self.type_value is None


@dataclass(frozen=True)
class Param(SerDeMixin):
    name: str
    type: MojoType


@dataclass(frozen=True)
class CallTarget(SerDeMixin):
    link_mode: LinkMode
    symbol: str


@dataclass
class FunctionDecl(SerDeMixin):
    SERDE = SerdeSpec(fields={"kind": SerdeFieldSpec(json_key="function_kind")})

    name: str
    link_name: str
    params: list[Param] = field(default_factory=list)
    return_type: MojoType = field(default_factory=lambda: BuiltinType(MojoBuiltin.NONE))
    kind: FunctionKind = FunctionKind.WRAPPER
    call_target: CallTarget = field(
        default_factory=lambda: CallTarget(link_mode=LinkMode.EXTERNAL_CALL, symbol="")
    )
    diagnostics: list[LoweringNote] = field(default_factory=list)


@dataclass
class GlobalDecl(SerDeMixin):
    SERDE = SerdeSpec(fields={"kind": SerdeFieldSpec(json_key="global_kind")})

    name: str
    link_name: str
    value_type: MojoType
    is_const: bool = False
    kind: GlobalKind = GlobalKind.WRAPPER
    diagnostics: list[LoweringNote] = field(default_factory=list)


MojoDecl = Union[
    StructDecl,
    AliasDecl,
    FunctionDecl,
    GlobalDecl,
]


@dataclass
class MojoModule(SerDeMixin):
    source_header: str
    library: str
    link_name: str
    link_mode: LinkMode
    capabilities: ModuleCapabilities = field(default_factory=ModuleCapabilities)
    decls: list[MojoDecl] = field(default_factory=list)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_json_dict(), indent=indent)


_MOJO_TYPE_FROM_JSON: dict[str, Callable[[dict[str, object]], MojoType]] = {
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


__all__ = [
    "AliasDecl",
    "AliasKind",
    "ArrayType",
    "BitfieldField",
    "BitfieldGroupMember",
    "BuiltinType",
    "CallTarget",
    "ConstExpr",
    "EnumMember",
    "FunctionDecl",
    "FunctionKind",
    "FunctionType",
    "GlobalDecl",
    "GlobalKind",
    "Initializer",
    "InitializerParam",
    "LinkMode",
    "LoweringNote",
    "ModuleCapabilities",
    "MojoBuiltin",
    "MojoDecl",
    "MojoModule",
    "MojoType",
    "NamedType",
    "OpaqueStorageMember",
    "PaddingMember",
    "Param",
    "ParametricType",
    "PointerMutability",
    "PointerOrigin",
    "PointerType",
    "StoredMember",
    "StructDecl",
    "StructKind",
    "StructMember",
    "FIXED_WIDTH_FLOAT_BUILTINS",
    "FIXED_WIDTH_INT_BUILTINS",
    "STD_FFI_FLOAT_BUILTINS",
    "STD_FFI_INT_BUILTINS",
    "const_expr_from_json",
    "mojo_decl_from_json",
    "mojo_type_from_json",
    "struct_member_from_json",
]

"""Minimal Mojo-centric IR for post-CIR lowering and Mojo code generation.

This module intentionally models emitted Mojo declaration forms rather than
mirroring the C-facing declaration taxonomy from :mod:`mojo_bindgen.ir`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar, Union

from mojo_bindgen.ir import FloatKind, IntKind
from mojo_bindgen.serde import SerdeFieldSpec, SerDeMixin, SerdeSpec


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


@dataclass
class ModuleCapabilities(SerDeMixin):
    needs_opaque_pointer_types: bool = False
    needs_atomic: bool = False
    needs_simd: bool = False
    needs_complex: bool = False
    needs_unsafe_union: bool = False
    needs_dl_handle_helpers: bool = False
    needs_global_helpers: bool = False


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
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(fields={"origin": SerdeFieldSpec(omit_if_default=True)})

    pointee: MojoType | None
    mutability: PointerMutability
    origin: PointerOrigin = PointerOrigin.EXTERNAL


@dataclass(frozen=True)
class ArrayType(SerDeMixin):
    element: MojoType
    count: int


@dataclass
class ParametricType(SerDeMixin):
    base: ParametricBase
    args: list[ParametricArg] = field(default_factory=list)


@dataclass(frozen=True)
class CallbackParam(SerDeMixin):
    name: str
    type: MojoType


@dataclass
class CallbackType(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "thin": SerdeFieldSpec(omit_if_default=True),
            "raises": SerdeFieldSpec(omit_if_default=True),
            "abi": SerdeFieldSpec(omit_if_default=True),
            "mutability": SerdeFieldSpec(omit_if_default=True),
            "origin": SerdeFieldSpec(omit_if_default=True),
        }
    )

    params: list[CallbackParam] = field(default_factory=list)
    ret: MojoType = field(default_factory=lambda: BuiltinType(MojoBuiltin.NONE))
    abi: str = "C"
    thin: bool = True
    raises: bool = False
    mutability: PointerMutability = PointerMutability.MUT
    origin: PointerOrigin = PointerOrigin.EXTERNAL


@dataclass
class FunctionType(SerDeMixin):
    params: list[MojoType] = field(default_factory=list)
    ret: MojoType = field(default_factory=lambda: BuiltinType(MojoBuiltin.NONE))


MojoType = Union[
    BuiltinType,
    NamedType,
    PointerType,
    ArrayType,
    ParametricType,
    CallbackType,
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


MojoConstExpr = Union[
    MojoIntLiteral,
    MojoFloatLiteral,
    MojoStringLiteral,
    MojoCharLiteral,
    MojoRefExpr,
    MojoUnaryExpr,
    MojoBinaryExpr,
    MojoCastExpr,
    MojoSizeOfExpr,
]


# TODO: check if size is needed here
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


class StructTraits(StrEnum):
    COPYABLE = "Copyable"
    IMPLICITLY_COPYABLE = "ImplicitlyCopyable"
    MOVABLE = "Movable"
    REGISTER_PASSABLE = "RegisterPassable"


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


# TODO: Enum is quite seperate from Struct now, move it out
@dataclass
class StructDecl(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "kind": SerdeFieldSpec(json_key="struct_kind"),
            "align_decorator": SerdeFieldSpec(omit_if_default=True),
            "underlying_type": SerdeFieldSpec(omit_if_default=True),
        }
    )

    name: str
    traits: list[StructTraits] = field(default_factory=list)
    align: int | None = None
    align_decorator: int | None = None
    fieldwise_init: bool = False
    kind: StructKind = StructKind.PLAIN
    members: list[StructMember] = field(default_factory=list)
    initializers: list[Initializer] = field(default_factory=list)
    diagnostics: list[LoweringNote] = field(default_factory=list)


@dataclass
class EnumDecl(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "align_decorator": SerdeFieldSpec(omit_if_default=True),
        }
    )
    name: str
    underlying_type: MojoType
    align_decorator: int | None = None
    enumerants: list[EnumMember] = field(default_factory=list)
    diagnostics: list[LoweringNote] = field(default_factory=list)


@dataclass
class AliasDecl(SerDeMixin):
    SERDE = SerdeSpec(fields={"kind": SerdeFieldSpec(json_key="alias_kind")})

    name: str
    kind: AliasKind
    type_value: MojoType | None = None
    const_value: MojoConstExpr | None = None
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
    EnumDecl,
    AliasDecl,
    FunctionDecl,
    GlobalDecl,
]


@dataclass
class MojoModule(SerDeMixin):
    SERDE: ClassVar[SerdeSpec] = SerdeSpec(
        fields={
            "imports": SerdeFieldSpec(omit_if_default=True),
            "support_decls": SerdeFieldSpec(omit_if_default=True),
        }
    )

    source_header: str
    library: str
    link_name: str
    link_mode: LinkMode
    capabilities: ModuleCapabilities = field(default_factory=ModuleCapabilities)
    imports: list[ModuleImport] = field(default_factory=list)
    support_decls: list[SupportDecl] = field(default_factory=list)
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
    "BuiltinType": BuiltinType.from_json_dict,
    "NamedType": NamedType.from_json_dict,
    "PointerType": PointerType.from_json_dict,
    "ArrayType": ArrayType.from_json_dict,
    "ParametricType": ParametricType.from_json_dict,
    "CallbackType": CallbackType.from_json_dict,
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
    "MojoIntLiteral": MojoIntLiteral.from_json_dict,
    "MojoFloatLiteral": MojoFloatLiteral.from_json_dict,
    "MojoStringLiteral": MojoStringLiteral.from_json_dict,
    "MojoCharLiteral": MojoCharLiteral.from_json_dict,
    "MojoRefExpr": MojoRefExpr.from_json_dict,
    "MojoUnaryExpr": MojoUnaryExpr.from_json_dict,
    "MojoBinaryExpr": MojoBinaryExpr.from_json_dict,
    "MojoCastExpr": MojoCastExpr.from_json_dict,
    "MojoSizeOfExpr": MojoSizeOfExpr.from_json_dict,
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
    "EnumDecl": EnumDecl.from_json_dict,
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
    "CallbackParam",
    "CallbackType",
    "ConstArg",
    "DTypeArg",
    "EnumDecl",
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
    "ModuleImport",
    "ModuleCapabilities",
    "MojoBinaryExpr",
    "MojoBuiltin",
    "MojoCastExpr",
    "MojoCharLiteral",
    "MojoConstExpr",
    "MojoDecl",
    "MojoFloatLiteral",
    "MojoIntLiteral",
    "MojoModule",
    "MojoRefExpr",
    "MojoSizeOfExpr",
    "MojoStringLiteral",
    "MojoType",
    "MojoUnaryExpr",
    "NameArg",
    "NamedType",
    "OpaqueStorageMember",
    "PaddingMember",
    "Param",
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
    "mojo_const_expr_from_json",
    "mojo_decl_from_json",
    "mojo_type_from_json",
    "parametric_arg_from_json",
    "struct_member_from_json",
]

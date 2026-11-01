"""Unversioned IR debug codecs; reflection is confined to this boundary."""

from __future__ import annotations

import json
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from functools import cache
from types import UnionType
from typing import Any, Literal, TypeAliasType, Union, cast, get_args, get_origin, get_type_hints

from mojo_bindgen import ir

type JSONValue = None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]

_NODES: dict[str, type] = {
    node.__name__: node
    for node in (
        ir.DocComment,
        ir.Qualifiers,
        ir.VoidType,
        ir.IntType,
        ir.FloatType,
        ir.QualifiedType,
        ir.AtomicType,
        ir.CPointer,
        ir.MojoPointer,
        ir.CArray,
        ir.MojoArray,
        ir.CFunctionPtr,
        ir.MojoFunctionPtr,
        ir.FunctionAttrs,
        ir.OpaqueRecordRef,
        ir.UnsupportedType,
        ir.ComplexType,
        ir.VectorType,
        ir.StructRef,
        ir.EnumRef,
        ir.TypeRef,
        ir.Field,
        ir.Struct,
        ir.IntLiteral,
        ir.CFloatLiteral,
        ir.MojoFloatLiteral,
        ir.StringLiteral,
        ir.CharLiteral,
        ir.CNullPtrLiteral,
        ir.CRefExpr,
        ir.MojoRefExpr,
        ir.CUnaryExpr,
        ir.MojoUnaryExpr,
        ir.CBinaryExpr,
        ir.MojoBinaryExpr,
        ir.CCastExpr,
        ir.MojoCastExpr,
        ir.CSizeOfExpr,
        ir.MojoSizeOfExpr,
        ir.CCallExpr,
        ir.MojoCallExpr,
        ir.Enumerant,
        ir.Enum,
        ir.Typedef,
        ir.CParam,
        ir.MojoParam,
        ir.Function,
        ir.Const,
        ir.MacroDecl,
        ir.GlobalVar,
        ir.IRDiagnostic,
        ir.TargetABI,
        ir.Unit,
        ir.PrimitiveDType,
        ir.MappingNote,
        ir.ModuleImport,
        ir.SupportDecl,
        ir.ModuleDependencies,
        ir.BuiltinType,
        ir.NamedType,
        ir.DTypeArg,
        ir.ConstArg,
        ir.NameArg,
        ir.TypeArg,
        ir.ParametricType,
        ir.StoredMember,
        ir.PaddingMember,
        ir.OpaqueStorageMember,
        ir.BitfieldField,
        ir.BitfieldGroupMember,
        ir.ComptimeMember,
        ir.InitializerParam,
        ir.Initializer,
        ir.FlexibleTail,
        ir.StructDecl,
        ir.AliasDecl,
        ir.CallTarget,
        ir.FunctionDecl,
        ir.GlobalDecl,
        ir.MojoModule,
    )
}

_FAMILIES: dict[TypeAliasType, dict[str, type]] = {
    family: {node.__name__: node for node in nodes}
    for family, nodes in (
        (
            ir.CType,
            (
                ir.VoidType,
                ir.IntType,
                ir.FloatType,
                ir.QualifiedType,
                ir.AtomicType,
                ir.CPointer,
                ir.CArray,
                ir.CFunctionPtr,
                ir.OpaqueRecordRef,
                ir.UnsupportedType,
                ir.ComplexType,
                ir.VectorType,
                ir.StructRef,
                ir.EnumRef,
                ir.TypeRef,
            ),
        ),
        (
            ir.MojoType,
            (
                ir.BuiltinType,
                ir.NamedType,
                ir.MojoPointer,
                ir.MojoArray,
                ir.MojoFunctionPtr,
                ir.ParametricType,
            ),
        ),
        (
            ir.CConstExpr,
            (
                ir.IntLiteral,
                ir.CFloatLiteral,
                ir.StringLiteral,
                ir.CharLiteral,
                ir.CNullPtrLiteral,
                ir.CRefExpr,
                ir.CUnaryExpr,
                ir.CBinaryExpr,
                ir.CCastExpr,
                ir.CSizeOfExpr,
                ir.CCallExpr,
            ),
        ),
        (
            ir.MojoConstExpr,
            (
                ir.IntLiteral,
                ir.MojoFloatLiteral,
                ir.StringLiteral,
                ir.CharLiteral,
                ir.MojoRefExpr,
                ir.MojoUnaryExpr,
                ir.MojoBinaryExpr,
                ir.MojoCastExpr,
                ir.MojoSizeOfExpr,
                ir.MojoCallExpr,
            ),
        ),
    )
}


def _encode(value: object) -> JSONValue:
    if isinstance(value, Enum):
        return _encode(value.value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (tuple, list)):
        return [_encode(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "kind": type(value).__name__,
            "fields": {f.name: _encode(getattr(value, f.name)) for f in fields(value)},
        }
    raise ValueError(f"cannot encode IR value {type(value).__name__}")


def to_debug_dict(value: object) -> dict[str, JSONValue]:
    encoded = _encode(value)
    if not isinstance(encoded, dict):
        raise ValueError("expected an IR record")
    return encoded


@cache
def _annotations(cls: type) -> dict[str, Any]:
    return get_type_hints(cls)


def _decode(raw: object, expected: Any) -> Any:
    if isinstance(expected, TypeAliasType):
        family = _FAMILIES.get(expected)
        if family is not None:
            tag = raw.get("kind") if isinstance(raw, dict) else None
            if not isinstance(tag, str) or tag not in family:
                raise ValueError(f"kind {tag!r} does not belong to {expected.__name__}")
            return _decode(raw, family[tag])
        return _decode(raw, expected.__value__)
    origin = get_origin(expected)
    args = get_args(expected)
    if origin in (Union, UnionType):
        for candidate in args:
            try:
                return _decode(raw, candidate)
            except (ValueError, TypeError):
                pass
        raise ValueError(f"value does not belong to {expected}")
    if origin is Literal:
        if raw not in args:
            raise ValueError(f"expected one of {args}")
        return raw
    if origin is tuple:
        if not isinstance(raw, list):
            raise ValueError("expected a JSON array")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(item, args[0]) for item in raw)
        if len(raw) != len(args):
            raise ValueError("incorrect tuple length")
        return tuple(_decode(item, element) for item, element in zip(raw, args, strict=True))
    if expected is type(None):
        if raw is not None:
            raise ValueError("expected null")
        return None
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(raw)
    if expected in (str, bool, int, float):
        if expected is float and isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
        if type(raw) is not expected:
            raise ValueError(f"expected {expected.__name__}")
        return raw
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(raw, dict):
            raise ValueError("expected an IR record")
        tag = raw.get("kind")
        if not isinstance(tag, str) or _NODES.get(tag) is not expected:
            raise ValueError(f"expected {expected.__name__}, got {tag!r}")
        payload = raw.get("fields")
        if set(raw) != {"kind", "fields"} or not isinstance(payload, dict):
            raise ValueError("expected kind and fields")
        declared = {f.name: f for f in fields(expected)}
        if payload.keys() - declared.keys():
            raise ValueError(f"unknown {tag} fields: {sorted(payload.keys() - declared.keys())}")
        annotations = _annotations(expected)
        kwargs = {}
        for name, field in declared.items():
            if name in payload:
                kwargs[name] = _decode(payload[name], annotations[name])
            elif field.default is MISSING and field.default_factory is MISSING:
                raise ValueError(f"missing {tag}.{name}")
        return expected(**kwargs)
    raise ValueError(f"unsupported IR field type {expected}")


def decode_node[T](raw: object, expected: type[T]) -> T:
    return cast(T, _decode(raw, expected))


def decode_c_type(raw: object) -> ir.CType:
    return cast(ir.CType, _decode(raw, ir.CType))


def decode_mojo_type(raw: object) -> ir.MojoType:
    return cast(ir.MojoType, _decode(raw, ir.MojoType))


def decode_c_expr(raw: object) -> ir.CConstExpr:
    return cast(ir.CConstExpr, _decode(raw, ir.CConstExpr))


def decode_mojo_expr(raw: object) -> ir.MojoConstExpr:
    return cast(ir.MojoConstExpr, _decode(raw, ir.MojoConstExpr))


def encode_cir(unit: ir.Unit) -> dict[str, JSONValue]:
    return to_debug_dict(unit)


def decode_cir(raw: object) -> ir.Unit:
    return decode_node(raw, ir.Unit)


def encode_mojo_ir(module: ir.MojoModule) -> dict[str, JSONValue]:
    return to_debug_dict(module)


def decode_mojo_ir(raw: object) -> ir.MojoModule:
    return decode_node(raw, ir.MojoModule)


def dumps_cir(unit: ir.Unit, *, indent: int | None = 2) -> str:
    return json.dumps(encode_cir(unit), indent=indent)


def loads_cir(text: str) -> ir.Unit:
    return decode_cir(json.loads(text))


def dumps_mojo_ir(module: ir.MojoModule, *, indent: int | None = 2) -> str:
    return json.dumps(encode_mojo_ir(module), indent=indent)


def loads_mojo_ir(text: str) -> ir.MojoModule:
    return decode_mojo_ir(json.loads(text))

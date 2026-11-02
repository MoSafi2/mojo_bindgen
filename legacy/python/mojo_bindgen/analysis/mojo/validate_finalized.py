"""Contracts required by the target-only printer after normalization."""

from __future__ import annotations

from typing import assert_never

from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    BitfieldGroupMember,
    BuiltinType,
    CharLiteral,
    FunctionDecl,
    FunctionKind,
    GlobalDecl,
    GlobalKind,
    InlineDisposition,
    IntLiteral,
    LinkMode,
    ModuleDependencies,
    MojoArray,
    MojoBinaryExpr,
    MojoBuiltin,
    MojoCallExpr,
    MojoCastExpr,
    MojoConstExpr,
    MojoFloatLiteral,
    MojoFunctionPtr,
    MojoModule,
    MojoPassability,
    MojoPointer,
    MojoRefExpr,
    MojoSizeOfExpr,
    MojoType,
    MojoUnaryExpr,
    NamedType,
    OpaqueStorageMember,
    OpaqueStorageType,
    PaddingMember,
    ParametricType,
    StoredMember,
    StringLiteral,
    StructDecl,
    StructKind,
    TypeArg,
)

from .record_policies import AssignRecordPoliciesPass


def _type(t: MojoType, *, callback: bool = False, active: set[int] | None = None) -> None:
    active = set() if active is None else active
    if id(t) in active:
        raise ValueError("structural MojoIR type cycle")
    active.add(id(t))
    try:
        match t:
            case BuiltinType() | NamedType():
                return
            case OpaqueStorageType():
                raise ValueError("unresolved opaque storage in finalized MojoIR")
            case MojoPointer():
                if t.pointee is not None:
                    _type(t.pointee, active=active)
            case MojoArray():
                _type(t.element, active=active)
            case ParametricType():
                for arg in t.args:
                    if isinstance(arg, TypeArg):
                        _type(arg.type, active=active)
            case MojoFunctionPtr():
                if not callback:
                    raise ValueError("unresolved callback signature in finalized MojoIR")
                if t.abi != "C" or not t.thin or t.raises:
                    raise ValueError(
                        "callback signature must be thin, non-raising and use the C ABI"
                    )
                _type(t.ret, active=active)
                for param in t.params:
                    _type(param.type, active=active)
            case _:
                assert_never(t)
    finally:
        active.remove(id(t))


def _expr(e: MojoConstExpr, active: set[int] | None = None) -> None:
    active = set() if active is None else active
    if id(e) in active:
        raise ValueError("structural MojoIR expression cycle")
    active.add(id(e))
    try:
        match e:
            case MojoUnaryExpr():
                _expr(e.operand, active)
            case MojoBinaryExpr():
                _expr(e.lhs, active)
                _expr(e.rhs, active)
            case MojoCastExpr():
                _type(e.target)
                _expr(e.expr, active)
            case MojoSizeOfExpr():
                _type(e.target)
            case MojoCallExpr():
                _expr(e.callee, active)
                for arg in e.args:
                    _expr(arg, active)
            case (
                IntLiteral() | MojoFloatLiteral() | StringLiteral() | CharLiteral() | MojoRefExpr()
            ):
                pass
            case _:
                assert_never(e)
    finally:
        active.remove(id(e))


def _extern_type(
    t: MojoType, records: dict[str, StructDecl], aliases: dict[str, AliasDecl], active: set[str]
) -> bool:
    match t:
        case BuiltinType():
            return t.name != MojoBuiltin.UNSUPPORTED
        case MojoPointer() | MojoFunctionPtr():
            return True
        case MojoArray():
            return t.size > 0 and _extern_type(t.element, records, aliases, active)
        case OpaqueStorageType() | ParametricType():
            return False
        case NamedType():
            if t.name in active:
                return False
            if t.name not in records and t.name not in aliases:
                return t.name in {
                    "Bool",
                    "Byte",
                    "Float16",
                    "Float32",
                    "Float64",
                    "Int",
                    "Int8",
                    "Int16",
                    "Int32",
                    "Int64",
                    "Int128",
                    "UInt",
                    "UInt8",
                    "UInt16",
                    "UInt32",
                    "UInt64",
                    "UInt128",
                }
            active.add(t.name)
            try:
                if t.name in aliases:
                    a = aliases[t.name]
                    return a.kind == AliasKind.CALLBACK_SIGNATURE or (
                        a.kind == AliasKind.TYPE_ALIAS
                        and a.type_value is not None
                        and _extern_type(a.type_value, records, aliases, active)
                    )
                record = records[t.name]
                return (
                    record.kind == StructKind.PLAIN
                    and record.flexible_tail is None
                    and bool(record.members)
                    and all(
                        isinstance(m, StoredMember)
                        and _extern_type(m.type, records, aliases, active)
                        for m in record.members
                    )
                )
            finally:
                active.remove(t.name)
    assert_never(t)


def validate_finalized_mojo_module(module: MojoModule, required: ModuleDependencies) -> None:
    actual = {(i.module, n) for i in module.dependencies.imports for n in i.names}
    for item in required.imports:
        for name in item.names:
            if (item.module, name) not in actual:
                raise ValueError(f"missing finalized import: {item.module}.{name}")
    supports = {s.kind for s in module.dependencies.support_decls}
    if any(s.kind not in supports for s in required.support_decls):
        raise ValueError("missing finalized support declaration")
    records = {d.name: d for d in module.decls if isinstance(d, StructDecl)}
    aliases = {d.name: d for d in module.decls if isinstance(d, AliasDecl)}
    policy = AssignRecordPoliciesPass()
    policy.run(module)
    names: set[str] = set()
    for decl in module.decls:
        emits = True
        match decl:
            case AliasDecl():
                emits = decl.type_value is not None or decl.const_value is not None
                if decl.kind == AliasKind.CALLBACK_SIGNATURE and not isinstance(
                    decl.type_value, MojoFunctionPtr
                ):
                    raise ValueError("callback alias has no function type: " + decl.name)
                if decl.type_value is not None:
                    _type(decl.type_value, callback=decl.kind == AliasKind.CALLBACK_SIGNATURE)
                if decl.const_type is not None:
                    _type(decl.const_type)
                if decl.const_value is not None:
                    _expr(decl.const_value)
            case GlobalDecl():
                emits = decl.kind == GlobalKind.WRAPPER
                _type(decl.value_type)
            case StructDecl():
                for member in decl.members:
                    match member:
                        case StoredMember():
                            _type(member.type)
                        case BitfieldGroupMember():
                            _type(member.storage_type)
                            for field in member.fields:
                                _type(field.logical_type)
                        case PaddingMember():
                            if (
                                member.storage_width_bytes not in (1, 2, 4, 8)
                                or member.storage_width_bytes != member.size_bytes
                            ):
                                raise ValueError("unresolved padding in finalized MojoIR")
                        case OpaqueStorageMember():
                            if member.size_bytes < 0:
                                raise ValueError("negative opaque storage size")
                        case _:
                            assert_never(member)
                for item in decl.comptime_members:
                    if item.type_value is not None:
                        _type(item.type_value)
                    if item.const_value is not None:
                        _expr(item.const_value)
                for init in decl.initializers:
                    for param in init.params:
                        _type(param.type)
                if decl.flexible_tail is not None:
                    _type(decl.flexible_tail.element_type)
            case FunctionDecl():
                emits = decl.kind in (FunctionKind.WRAPPER, FunctionKind.EXTERN_DECLARATION)
                _type(decl.return_type)
                for param in decl.params:
                    _type(param.type)
                if (
                    decl.kind == FunctionKind.WRAPPER
                    and policy._type_passability(decl.return_type) == MojoPassability.MEMORY_ONLY
                ):
                    raise ValueError("wrapper return is not RegisterPassable: " + decl.name)
                if emits and (
                    not (decl.call_target.symbol or decl.link_name)
                    or decl.attrs.inline_disposition != InlineDisposition.NONE
                ):
                    raise ValueError("invalid finalized callable: " + decl.name)
                if decl.kind == FunctionKind.EXTERN_DECLARATION:
                    if (
                        decl.call_target.link_mode != LinkMode.EXTERNAL_CALL
                        or decl.num_fixed_args is not None
                    ):
                        raise ValueError(
                            "external declaration requires fixed direct C linking: " + decl.name
                        )
                    if not all(
                        _extern_type(t, records, aliases, set())
                        for t in (decl.return_type, *(p.type for p in decl.params))
                    ):
                        raise ValueError(
                            "external declaration has an ineligible type: " + decl.name
                        )
                elif decl.kind == FunctionKind.WRAPPER and decl.num_fixed_args is not None:
                    if (
                        decl.call_target.link_mode != LinkMode.EXTERNAL_CALL
                        or decl.num_fixed_args != len(decl.params)
                    ):
                        raise ValueError("invalid finalized variadic call: " + decl.name)
            case _:
                assert_never(decl)
        if emits:
            if decl.name in names:
                raise ValueError("duplicate finalized declaration: " + decl.name)
            names.add(decl.name)

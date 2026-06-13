from __future__ import annotations

from dataclasses import replace

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.ir import (
    Array,
    AtomicType,
    BinaryExpr,
    CastExpr,
    ComplexType,
    Const,
    ConstExpr,
    Decl,
    Enum,
    EnumRef,
    Field,
    Function,
    FunctionPtr,
    GlobalVar,
    MacroDecl,
    Pointer,
    QualifiedType,
    RefExpr,
    SizeOfExpr,
    Struct,
    Type,
    Typedef,
    TypeRef,
    UnaryExpr,
    VectorType,
)
from mojo_bindgen.parsing.parser import Unit

type EnumResolution = tuple[str, tuple[str, ...]]


class CIRCanonicalizer:
    """Canonicalize cross-declaration CIR facts before Mojo mapping.

    This pass repairs parser-local declaration quirks without changing the
    caller-owned ``Unit``. Its ordered steps are:

    1. keep one record row per ``decl_id``, preferring complete definitions
    2. remove duplicate equivalent function declarations
    3. keep the last macro definition for repeated macro names
    4. drop self-alias macros already represented by constants/enumerants
    5. choose enum primary names and rewrite enum references to those names
    """

    def __init__(
        self,
    ) -> None:
        self._struct_by_usr: dict[str, Struct] = {}

    def canonicalize(self, unit: Unit) -> Unit:
        decls = self._dedupe_structs(unit)
        decls = _dedupe_functions(decls)
        decls = _dedupe_macros_last_wins(decls)
        decls = _drop_constant_self_alias_macros(decls)
        enum_names = _resolve_enum_names(decls)
        return replace(unit, decls=[_rewrite_decl(decl, enum_names) for decl in decls])

    def _dedupe_structs(self, unit: Unit) -> list[Decl]:
        out = list[Decl]()
        for decl in unit.decls:
            if isinstance(decl, Struct):
                if not self._struct_by_usr.get(decl.decl_id):
                    self._struct_by_usr[decl.decl_id] = decl

                self._struct_by_usr[decl.decl_id] = _compare(
                    decl, self._struct_by_usr[decl.decl_id]
                )
            else:
                out.append(decl)
        out.extend(self._struct_by_usr.values())
        return out


def _compare(new: Struct, old: Struct) -> Struct:
    if not new.is_complete:
        return old
    if not old.is_complete:
        return new
    return old


def _dedupe_functions(decls: list[Decl]) -> list[Decl]:
    out: list[Decl] = []
    seen: list[Function] = []
    for decl in decls:
        if not isinstance(decl, Function):
            out.append(decl)
            continue
        if any(_same_function_identity(decl, prev) for prev in seen):
            continue
        seen.append(decl)
        out.append(decl)
    return out


def _same_function_identity(a: Function, b: Function) -> bool:
    return (
        a.name == b.name
        and a.link_name == b.link_name
        and a.ret == b.ret
        and [p.type for p in a.params] == [p.type for p in b.params]
        and a.is_variadic == b.is_variadic
        and a.calling_convention == b.calling_convention
        and a.is_noreturn == b.is_noreturn
    )


def _dedupe_macros_last_wins(decls: list[Decl]) -> list[Decl]:
    out_reversed: list[Decl] = []
    seen_macro_names: set[str] = set()
    for decl in reversed(decls):
        if isinstance(decl, MacroDecl):
            if decl.name in seen_macro_names:
                continue
            seen_macro_names.add(decl.name)
        out_reversed.append(decl)
    out_reversed.reverse()
    return out_reversed


def _drop_constant_self_alias_macros(decls: list[Decl]) -> list[Decl]:
    claimed = _constant_like_names(decls)
    return [
        decl
        for decl in decls
        if not (
            isinstance(decl, MacroDecl)
            and isinstance(decl.expr, RefExpr)
            and decl.expr.name == decl.name
            and decl.name in claimed
        )
    ]


def _constant_like_names(decls: list[Decl]) -> set[str]:
    names: set[str] = set()
    for decl in decls:
        if isinstance(decl, Const):
            names.add(decl.name)
        elif isinstance(decl, Enum):
            names.update(enumerant.name for enumerant in decl.enumerants)
    return names


def _resolve_enum_names(decls: list[Decl]) -> dict[str, EnumResolution]:
    typedefs_by_enum: dict[str, list[str]] = {}
    enum_decls: dict[str, Enum] = {}
    ordinary_mojo_names: set[str] = set()
    for decl in decls:
        if isinstance(decl, Enum):
            enum_decls[decl.decl_id] = decl
            ordinary_mojo_names.update(mojo_ident(enumerant.name) for enumerant in decl.enumerants)
        elif isinstance(decl, Typedef):
            ordinary_mojo_names.add(mojo_ident(decl.name))
            ref = _enum_ref_from_type(decl.aliased) or _enum_ref_from_type(decl.canonical)
            if ref is not None:
                typedefs_by_enum.setdefault(ref.decl_id, []).append(decl.name)
        elif isinstance(decl, (Struct, Function, GlobalVar, Const, MacroDecl)):
            ordinary_mojo_names.add(mojo_ident(decl.name))

    names: dict[str, EnumResolution] = {}
    claimed_enum_names: set[str] = set()
    for decl in decls:
        if not isinstance(decl, Enum):
            continue
        decl_id = decl.decl_id
        enum_decl = enum_decls[decl_id]
        typedef_names = typedefs_by_enum.get(decl_id, [])
        tag_name = enum_decl.c_name if not enum_decl.is_anonymous and enum_decl.c_name else None
        primary_name = typedef_names[0] if typedef_names else (tag_name or enum_decl.name)
        primary_ident = mojo_ident(primary_name)
        alias_names: list[str] = []
        if tag_name is not None:
            tag_ident = mojo_ident(tag_name)
            if (
                tag_ident != primary_ident
                and tag_ident not in ordinary_mojo_names
                and tag_ident not in claimed_enum_names
            ):
                alias_names.append(tag_name)
                claimed_enum_names.add(tag_ident)
        claimed_enum_names.add(primary_ident)
        names[decl_id] = (primary_name, tuple(alias_names))
    return names


def _enum_ref_from_type(t: Type) -> EnumRef | None:
    if isinstance(t, EnumRef):
        return t
    if isinstance(t, TypeRef):
        return _enum_ref_from_type(t.canonical)
    return None


def _rewrite_decl(
    decl: Decl,
    enum_names: dict[str, EnumResolution],
) -> Decl:
    if isinstance(decl, Enum):
        resolved = enum_names.get(decl.decl_id)
        if resolved is None:
            return decl
        primary_name, alias_names = resolved
        return replace(
            decl,
            name=primary_name,
            alias_names=list(alias_names),
            enumerants=[
                replace(enumerant, enum_decl_id=decl.decl_id) for enumerant in decl.enumerants
            ],
        )
    if isinstance(decl, Typedef):
        return replace(
            decl,
            aliased=_rewrite_type(decl.aliased, enum_names),
            canonical=_rewrite_type(decl.canonical, enum_names),
        )
    if isinstance(decl, Struct):
        return replace(
            decl,
            fields=[_rewrite_field(field, enum_names) for field in decl.fields],
        )
    if isinstance(decl, Function):
        return replace(
            decl,
            ret=_rewrite_type(decl.ret, enum_names),
            params=[
                replace(param, type=_rewrite_type(param.type, enum_names)) for param in decl.params
            ],
        )
    if isinstance(decl, GlobalVar):
        return replace(decl, type=_rewrite_type(decl.type, enum_names))
    if isinstance(decl, Const):
        return replace(
            decl,
            type=_rewrite_type(decl.type, enum_names),
            expr=_rewrite_const_expr(decl.expr, enum_names),
        )
    if isinstance(decl, MacroDecl):
        return replace(
            decl,
            type=(None if decl.type is None else _rewrite_type(decl.type, enum_names)),
            expr=(None if decl.expr is None else _rewrite_const_expr(decl.expr, enum_names)),
        )
    return decl


def _rewrite_field(
    field: Field,
    enum_names: dict[str, EnumResolution],
) -> Field:
    return replace(field, type=_rewrite_type(field.type, enum_names))


def _rewrite_type(
    t: Type,
    enum_names: dict[str, EnumResolution],
) -> Type:
    if isinstance(t, EnumRef):
        resolved = enum_names.get(t.decl_id)
        if resolved is None:
            return t
        primary_name, _alias_names = resolved
        return replace(t, name=primary_name)
    if isinstance(t, TypeRef):
        return replace(t, canonical=_rewrite_type(t.canonical, enum_names))
    if isinstance(t, QualifiedType):
        return replace(t, unqualified=_rewrite_type(t.unqualified, enum_names))
    if isinstance(t, AtomicType):
        return replace(t, value_type=_rewrite_type(t.value_type, enum_names))
    if isinstance(t, Pointer):
        return replace(
            t,
            pointee=(None if t.pointee is None else _rewrite_type(t.pointee, enum_names)),
        )
    if isinstance(t, Array):
        return replace(t, element=_rewrite_type(t.element, enum_names))
    if isinstance(t, FunctionPtr):
        return replace(
            t,
            ret=_rewrite_type(t.ret, enum_names),
            params=[
                replace(param, type=_rewrite_type(param.type, enum_names)) for param in t.params
            ],
        )
    if isinstance(t, ComplexType):
        return t
    if isinstance(t, VectorType):
        return replace(t, element=_rewrite_type(t.element, enum_names))
    return t


def _rewrite_const_expr(
    expr: ConstExpr,
    enum_names: dict[str, EnumResolution],
) -> ConstExpr:
    if isinstance(expr, CastExpr):
        return replace(
            expr,
            target=_rewrite_type(expr.target, enum_names),
            expr=_rewrite_const_expr(expr.expr, enum_names),
        )
    if isinstance(expr, SizeOfExpr):
        return replace(expr, target=_rewrite_type(expr.target, enum_names))
    if isinstance(expr, UnaryExpr):
        return replace(expr, operand=_rewrite_const_expr(expr.operand, enum_names))
    if isinstance(expr, BinaryExpr):
        return replace(
            expr,
            lhs=_rewrite_const_expr(expr.lhs, enum_names),
            rhs=_rewrite_const_expr(expr.rhs, enum_names),
        )
    return expr

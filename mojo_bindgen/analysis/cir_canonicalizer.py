from __future__ import annotations

from dataclasses import replace

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
    SizeOfExpr,
    Struct,
    Type,
    Typedef,
    TypeRef,
    UnaryExpr,
    VectorType,
)
from mojo_bindgen.parsing.parser import Unit


class CIRCanonicalizer:
    """Canonicalize cross-declaration CIR facts before Mojo lowering."""

    def __init__(
        self,
    ) -> None:
        self._struct_by_usr: dict[str, Struct] = {}

    def canonicalize(self, unit: Unit) -> Unit:
        decls = self._dedupe_structs(unit)
        enum_names = _resolve_enum_names(decls)
        unit.decls = [_rewrite_decl(decl, enum_names) for decl in decls]
        return unit

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


def _resolve_enum_names(decls: list[Decl]) -> dict[str, tuple[str, str | None, str | None]]:
    typedefs_by_enum: dict[str, list[str]] = {}
    enum_decls: dict[str, Enum] = {}
    for decl in decls:
        if isinstance(decl, Enum):
            enum_decls[decl.decl_id] = decl
        elif isinstance(decl, Typedef):
            ref = _enum_ref_from_type(decl.aliased) or _enum_ref_from_type(decl.canonical)
            if ref is not None:
                typedefs_by_enum.setdefault(ref.decl_id, []).append(decl.name)

    names: dict[str, tuple[str, str | None, str | None]] = {}
    for decl_id, enum_decl in enum_decls.items():
        typedef_names = typedefs_by_enum.get(decl_id, [])
        tag_name = enum_decl.tag_name
        if tag_name is None and not enum_decl.is_anonymous and enum_decl.c_name:
            tag_name = enum_decl.c_name
        public_name = typedef_names[0] if typedef_names else enum_decl.public_name
        if public_name:
            mojo_name = public_name
        elif tag_name:
            mojo_name = f"enum_{tag_name}"
        else:
            mojo_name = enum_decl.name
        names[decl_id] = (mojo_name, tag_name, public_name)
    return names


def _enum_ref_from_type(t: Type) -> EnumRef | None:
    if isinstance(t, EnumRef):
        return t
    if isinstance(t, TypeRef):
        return _enum_ref_from_type(t.canonical)
    return None


def _rewrite_decl(
    decl: Decl,
    enum_names: dict[str, tuple[str, str | None, str | None]],
) -> Decl:
    if isinstance(decl, Enum):
        resolved = enum_names.get(decl.decl_id)
        if resolved is None:
            return decl
        mojo_name, tag_name, public_name = resolved
        return replace(
            decl,
            name=mojo_name,
            tag_name=tag_name,
            public_name=public_name,
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
    enum_names: dict[str, tuple[str, str | None, str | None]],
) -> Field:
    return replace(field, type=_rewrite_type(field.type, enum_names))


def _rewrite_type(
    t: Type,
    enum_names: dict[str, tuple[str, str | None, str | None]],
) -> Type:
    if isinstance(t, EnumRef):
        resolved = enum_names.get(t.decl_id)
        if resolved is None:
            return t
        mojo_name, tag_name, public_name = resolved
        return replace(t, name=mojo_name, tag_name=tag_name, public_name=public_name)
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
            params=[_rewrite_type(param, enum_names) for param in t.params],
        )
    if isinstance(t, ComplexType):
        return t
    if isinstance(t, VectorType):
        return replace(t, element=_rewrite_type(t.element, enum_names))
    return t


def _rewrite_const_expr(
    expr: ConstExpr,
    enum_names: dict[str, tuple[str, str | None, str | None]],
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

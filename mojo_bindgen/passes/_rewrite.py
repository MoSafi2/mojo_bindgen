"""Shared IR rebuilding helpers for Unit-to-Unit passes."""

from __future__ import annotations

from mojo_bindgen.ir import (
    Array,
    AtomicType,
    BinaryExpr,
    CastExpr,
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
    OpaqueRecordRef,
    Param,
    Pointer,
    QualifiedType,
    RefExpr,
    SizeOfExpr,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Typedef,
    UnaryExpr,
    Unit,
)


def rewrite_type(t: Type, *, rewrite_decl_id: bool = False) -> Type:
    """Return a recursively rebuilt IR type."""
    if isinstance(t, QualifiedType):
        return QualifiedType(
            unqualified=rewrite_type(t.unqualified, rewrite_decl_id=rewrite_decl_id),
            qualifiers=t.qualifiers,
        )
    if isinstance(t, AtomicType):
        return AtomicType(value_type=rewrite_type(t.value_type, rewrite_decl_id=rewrite_decl_id))
    if isinstance(t, Pointer):
        pointee = None if t.pointee is None else rewrite_type(t.pointee, rewrite_decl_id=rewrite_decl_id)
        return Pointer(pointee=pointee)
    if isinstance(t, Array):
        return Array(
            element=rewrite_type(t.element, rewrite_decl_id=rewrite_decl_id),
            size=t.size,
            array_kind=t.array_kind,
        )
    if isinstance(t, FunctionPtr):
        return FunctionPtr(
            ret=rewrite_type(t.ret, rewrite_decl_id=rewrite_decl_id),
            params=[rewrite_type(p, rewrite_decl_id=rewrite_decl_id) for p in t.params],
            param_names=None if t.param_names is None else list(t.param_names),
            is_variadic=t.is_variadic,
            calling_convention=t.calling_convention,
            is_noreturn=t.is_noreturn,
        )
    if isinstance(t, OpaqueRecordRef):
        return OpaqueRecordRef(
            decl_id=t.name if rewrite_decl_id and not t.decl_id else t.decl_id,
            name=t.name,
            c_name=t.c_name,
            is_union=t.is_union,
        )
    if isinstance(t, StructRef):
        return StructRef(
            decl_id=t.name if rewrite_decl_id and not t.decl_id else t.decl_id,
            name=t.name,
            c_name=t.c_name,
            is_union=t.is_union,
            size_bytes=t.size_bytes,
            is_anonymous=t.is_anonymous,
        )
    if isinstance(t, EnumRef):
        return EnumRef(
            decl_id=t.name if rewrite_decl_id and not t.decl_id else t.decl_id,
            name=t.name,
            c_name=t.c_name,
            underlying=t.underlying,
        )
    if isinstance(t, TypeRef):
        return TypeRef(
            decl_id=t.name if rewrite_decl_id and not t.decl_id else t.decl_id,
            name=t.name,
            canonical=rewrite_type(t.canonical, rewrite_decl_id=rewrite_decl_id),
        )
    return t


def rewrite_const_expr(expr: ConstExpr, *, rewrite_decl_id: bool = False) -> ConstExpr:
    """Return a recursively rebuilt constant-expression node."""
    if isinstance(expr, UnaryExpr):
        return UnaryExpr(op=expr.op, operand=rewrite_const_expr(expr.operand, rewrite_decl_id=rewrite_decl_id))
    if isinstance(expr, BinaryExpr):
        return BinaryExpr(
            op=expr.op,
            lhs=rewrite_const_expr(expr.lhs, rewrite_decl_id=rewrite_decl_id),
            rhs=rewrite_const_expr(expr.rhs, rewrite_decl_id=rewrite_decl_id),
        )
    if isinstance(expr, CastExpr):
        return CastExpr(
            target=rewrite_type(expr.target, rewrite_decl_id=rewrite_decl_id),
            expr=rewrite_const_expr(expr.expr, rewrite_decl_id=rewrite_decl_id),
        )
    if isinstance(expr, SizeOfExpr):
        return SizeOfExpr(target=rewrite_type(expr.target, rewrite_decl_id=rewrite_decl_id))
    if isinstance(expr, RefExpr):
        return RefExpr(name=expr.name)
    return expr


def rewrite_decl(decl: Decl, *, rewrite_decl_id: bool = False) -> Decl:
    """Return a recursively rebuilt top-level declaration."""
    if isinstance(decl, Struct):
        return Struct(
            decl_id=decl.name if rewrite_decl_id and not decl.decl_id else decl.decl_id,
            name=decl.name,
            c_name=decl.c_name,
            fields=[
                Field(
                    name=f.name,
                    source_name=f.source_name,
                    type=rewrite_type(f.type, rewrite_decl_id=rewrite_decl_id),
                    byte_offset=f.byte_offset,
                    is_anonymous=f.is_anonymous,
                    is_bitfield=f.is_bitfield,
                    bit_offset=f.bit_offset,
                    bit_width=f.bit_width,
                )
                for f in decl.fields
            ],
            size_bytes=decl.size_bytes,
            align_bytes=decl.align_bytes,
            is_union=decl.is_union,
            is_anonymous=decl.is_anonymous,
            is_complete=decl.is_complete,
            is_packed=decl.is_packed,
            requested_align_bytes=decl.requested_align_bytes,
        )
    if isinstance(decl, Enum):
        return Enum(
            decl_id=decl.name if rewrite_decl_id and not decl.decl_id else decl.decl_id,
            name=decl.name,
            c_name=decl.c_name,
            underlying=decl.underlying,
            enumerants=list(decl.enumerants),
        )
    if isinstance(decl, Typedef):
        return Typedef(
            decl_id=decl.name if rewrite_decl_id and not decl.decl_id else decl.decl_id,
            name=decl.name,
            aliased=rewrite_type(decl.aliased, rewrite_decl_id=rewrite_decl_id),
            canonical=rewrite_type(decl.canonical, rewrite_decl_id=rewrite_decl_id),
        )
    if isinstance(decl, Function):
        return Function(
            decl_id=decl.name if rewrite_decl_id and not decl.decl_id else decl.decl_id,
            name=decl.name,
            link_name=decl.link_name,
            ret=rewrite_type(decl.ret, rewrite_decl_id=rewrite_decl_id),
            params=[
                Param(name=p.name, type=rewrite_type(p.type, rewrite_decl_id=rewrite_decl_id))
                for p in decl.params
            ],
            is_variadic=decl.is_variadic,
            calling_convention=decl.calling_convention,
            is_noreturn=decl.is_noreturn,
        )
    if isinstance(decl, Const):
        return Const(
            name=decl.name,
            type=rewrite_type(decl.type, rewrite_decl_id=rewrite_decl_id),
            expr=rewrite_const_expr(decl.expr, rewrite_decl_id=rewrite_decl_id),
        )
    if isinstance(decl, MacroDecl):
        return MacroDecl(
            name=decl.name,
            tokens=list(decl.tokens),
            kind=decl.kind,
            expr=None if decl.expr is None else rewrite_const_expr(decl.expr, rewrite_decl_id=rewrite_decl_id),
            type=None if decl.type is None else rewrite_type(decl.type, rewrite_decl_id=rewrite_decl_id),
            diagnostic=decl.diagnostic,
        )
    if isinstance(decl, GlobalVar):
        return GlobalVar(
            decl_id=decl.name if rewrite_decl_id and not decl.decl_id else decl.decl_id,
            name=decl.name,
            link_name=decl.link_name,
            type=rewrite_type(decl.type, rewrite_decl_id=rewrite_decl_id),
            is_const=decl.is_const,
            initializer=None
            if decl.initializer is None
            else rewrite_const_expr(decl.initializer, rewrite_decl_id=rewrite_decl_id),
        )
    return decl


def rewrite_unit(unit: Unit, *, rewrite_decl_id: bool = False) -> Unit:
    """Return a rebuilt unit for pure Unit-to-Unit passes."""
    return Unit(
        source_header=unit.source_header,
        library=unit.library,
        link_name=unit.link_name,
        decls=[rewrite_decl(decl, rewrite_decl_id=rewrite_decl_id) for decl in unit.decls],
        diagnostics=list(unit.diagnostics),
    )

"""IR pass that resolves decl/name/c_name relationships against Unit declarations."""

from __future__ import annotations

from mojo_bindgen.ir import (
    Array,
    AtomicType,
    CastExpr,
    Const,
    Enum,
    EnumRef,
    Function,
    FunctionPtr,
    GlobalVar,
    MacroDecl,
    OpaqueRecordRef,
    Pointer,
    QualifiedType,
    SizeOfExpr,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Typedef,
    Unit,
)


class ResolveDeclRefsPass:
    """Resolve declaration references and normalize identity-bearing metadata."""

    def run(self, unit: Unit) -> Unit:
        typedefs_by_id = {
            decl.decl_id: decl for decl in unit.decls if isinstance(decl, Typedef) and decl.decl_id
        }
        typedefs_by_name = {decl.name: decl for decl in unit.decls if isinstance(decl, Typedef)}
        structs_by_id = {
            decl.decl_id: decl for decl in unit.decls if isinstance(decl, Struct) and decl.decl_id
        }
        structs_by_name = {
            name: decl
            for decl in unit.decls
            if isinstance(decl, Struct)
            for name in filter(None, {decl.name, decl.c_name})
        }
        enums_by_id = {
            decl.decl_id: decl for decl in unit.decls if isinstance(decl, Enum) and decl.decl_id
        }
        enums_by_name = {
            name: decl
            for decl in unit.decls
            if isinstance(decl, Enum)
            for name in filter(None, {decl.name, decl.c_name})
        }
        return Unit(
            source_header=unit.source_header,
            library=unit.library,
            link_name=unit.link_name,
            decls=[
                self._resolve_decl(
                    decl,
                    typedefs_by_id=typedefs_by_id,
                    typedefs_by_name=typedefs_by_name,
                    structs_by_id=structs_by_id,
                    structs_by_name=structs_by_name,
                    enums_by_id=enums_by_id,
                    enums_by_name=enums_by_name,
                )
                for decl in unit.decls
            ],
            diagnostics=list(unit.diagnostics),
        )

    def _resolve_decl(self, decl, **maps):
        if isinstance(decl, Struct):
            decl_id = decl.decl_id or decl.name or decl.c_name
            name = decl.name or decl.c_name or decl_id
            c_name = decl.c_name or decl.name or name
            return Struct(
                decl_id=decl_id,
                name=name,
                c_name=c_name,
                fields=[
                    field.__class__(
                        name=field.name,
                        source_name=field.source_name,
                        type=self._resolve_type(field.type, **maps),
                        byte_offset=field.byte_offset,
                        is_anonymous=field.is_anonymous,
                        is_bitfield=field.is_bitfield,
                        bit_offset=field.bit_offset,
                        bit_width=field.bit_width,
                    )
                    for field in decl.fields
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
            decl_id = decl.decl_id or decl.name or decl.c_name
            name = decl.name or decl.c_name or decl_id
            c_name = decl.c_name or decl.name or name
            return Enum(
                decl_id=decl_id,
                name=name,
                c_name=c_name,
                underlying=decl.underlying,
                enumerants=list(decl.enumerants),
            )
        if isinstance(decl, Typedef):
            decl_id = decl.decl_id or decl.name
            name = decl.name or decl_id
            return Typedef(
                decl_id=decl_id,
                name=name,
                aliased=self._resolve_type(decl.aliased, **maps),
                canonical=self._resolve_type(decl.canonical, **maps),
            )
        if isinstance(decl, Function):
            decl_id = decl.decl_id or decl.name or decl.link_name
            name = decl.name or decl.link_name or decl_id
            link_name = decl.link_name or decl.name or decl_id
            return Function(
                decl_id=decl_id,
                name=name,
                link_name=link_name,
                ret=self._resolve_type(decl.ret, **maps),
                params=[
                    param.__class__(name=param.name, type=self._resolve_type(param.type, **maps))
                    for param in decl.params
                ],
                is_variadic=decl.is_variadic,
                calling_convention=decl.calling_convention,
                is_noreturn=decl.is_noreturn,
            )
        if isinstance(decl, GlobalVar):
            decl_id = decl.decl_id or decl.name or decl.link_name
            name = decl.name or decl.link_name or decl_id
            link_name = decl.link_name or decl.name or decl_id
            return GlobalVar(
                decl_id=decl_id,
                name=name,
                link_name=link_name,
                type=self._resolve_type(decl.type, **maps),
                is_const=decl.is_const,
                initializer=self._resolve_const_expr(decl.initializer, **maps),
            )
        if isinstance(decl, Const):
            return Const(
                name=decl.name,
                type=self._resolve_type(decl.type, **maps),
                expr=self._resolve_const_expr(decl.expr, **maps),
            )
        if isinstance(decl, MacroDecl):
            return MacroDecl(
                name=decl.name,
                tokens=list(decl.tokens),
                kind=decl.kind,
                expr=self._resolve_const_expr(decl.expr, **maps),
                type=None if decl.type is None else self._resolve_type(decl.type, **maps),
                diagnostic=decl.diagnostic,
            )
        return decl

    def _resolve_const_expr(self, expr, **maps):
        if expr is None:
            return None
        if isinstance(expr, CastExpr):
            return CastExpr(target=self._resolve_type(expr.target, **maps), expr=self._resolve_const_expr(expr.expr, **maps))
        if isinstance(expr, SizeOfExpr):
            return SizeOfExpr(target=self._resolve_type(expr.target, **maps))
        if hasattr(expr, "operand"):
            return expr.__class__(op=expr.op, operand=self._resolve_const_expr(expr.operand, **maps))
        if hasattr(expr, "lhs") and hasattr(expr, "rhs"):
            return expr.__class__(
                op=expr.op,
                lhs=self._resolve_const_expr(expr.lhs, **maps),
                rhs=self._resolve_const_expr(expr.rhs, **maps),
            )
        return expr

    def _resolve_type(self, t: Type, **maps) -> Type:
        if isinstance(t, QualifiedType):
            return QualifiedType(unqualified=self._resolve_type(t.unqualified, **maps), qualifiers=t.qualifiers)
        if isinstance(t, AtomicType):
            return AtomicType(value_type=self._resolve_type(t.value_type, **maps))
        if isinstance(t, Pointer):
            return Pointer(pointee=None if t.pointee is None else self._resolve_type(t.pointee, **maps))
        if isinstance(t, Array):
            return Array(element=self._resolve_type(t.element, **maps), size=t.size, array_kind=t.array_kind)
        if isinstance(t, FunctionPtr):
            return FunctionPtr(
                ret=self._resolve_type(t.ret, **maps),
                params=[self._resolve_type(param, **maps) for param in t.params],
                param_names=None if t.param_names is None else list(t.param_names),
                is_variadic=t.is_variadic,
                calling_convention=t.calling_convention,
                is_noreturn=t.is_noreturn,
            )
        if isinstance(t, TypeRef):
            target = maps["typedefs_by_id"].get(t.decl_id) if t.decl_id else None
            if target is None and t.name:
                target = maps["typedefs_by_name"].get(t.name)
            return TypeRef(
                decl_id=t.decl_id or ("" if target is None else target.decl_id),
                name=t.name or ("" if target is None else target.name),
                canonical=self._resolve_type(
                    t.canonical if target is None else target.canonical,
                    **maps,
                ),
            )
        if isinstance(t, StructRef):
            target = maps["structs_by_id"].get(t.decl_id) if t.decl_id else None
            if target is None:
                target = maps["structs_by_name"].get(t.name) or maps["structs_by_name"].get(t.c_name)
            return StructRef(
                decl_id=t.decl_id or ("" if target is None else target.decl_id),
                name=t.name or ("" if target is None else target.name),
                c_name=t.c_name or ("" if target is None else target.c_name),
                is_union=t.is_union if target is None else target.is_union,
                size_bytes=t.size_bytes if t.size_bytes or target is None else target.size_bytes,
                is_anonymous=t.is_anonymous if target is None else target.is_anonymous,
            )
        if isinstance(t, OpaqueRecordRef):
            target = maps["structs_by_id"].get(t.decl_id) if t.decl_id else None
            if target is None:
                target = maps["structs_by_name"].get(t.name) or maps["structs_by_name"].get(t.c_name)
            return OpaqueRecordRef(
                decl_id=t.decl_id or ("" if target is None else target.decl_id),
                name=t.name or ("" if target is None else target.name),
                c_name=t.c_name or ("" if target is None else target.c_name),
                is_union=t.is_union if target is None else target.is_union,
            )
        if isinstance(t, EnumRef):
            target = maps["enums_by_id"].get(t.decl_id) if t.decl_id else None
            if target is None and t.name:
                target = maps["enums_by_name"].get(t.name) or maps["enums_by_name"].get(t.c_name)
            return EnumRef(
                decl_id=t.decl_id or ("" if target is None else target.decl_id),
                name=t.name or ("" if target is None else target.name),
                c_name=t.c_name or ("" if target is None else target.c_name),
                underlying=t.underlying if target is None else target.underlying,
            )
        return t

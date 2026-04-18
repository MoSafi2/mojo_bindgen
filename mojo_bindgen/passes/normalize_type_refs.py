"""IR pass that canonicalizes typedef-backed type trees."""

from __future__ import annotations

from mojo_bindgen.ir import (
    Array,
    AtomicType,
    CastExpr,
    Const,
    Enum,
    Function,
    FunctionPtr,
    GlobalVar,
    MacroDecl,
    Pointer,
    QualifiedType,
    SizeOfExpr,
    Struct,
    Type,
    TypeRef,
    Typedef,
    Unit,
)


class NormalizeTypeRefsPass:
    """Normalize nested types and fully canonicalize typedef-backed references."""

    def run(self, unit: Unit) -> Unit:
        typedefs_by_id = {
            decl.decl_id: decl for decl in unit.decls if isinstance(decl, Typedef) and decl.decl_id
        }
        typedefs_by_name = {decl.name: decl for decl in unit.decls if isinstance(decl, Typedef)}
        return Unit(
            source_header=unit.source_header,
            library=unit.library,
            link_name=unit.link_name,
            decls=[
                self._normalize_decl(decl, typedefs_by_id, typedefs_by_name) for decl in unit.decls
            ],
            diagnostics=list(unit.diagnostics),
        )

    def _normalize_decl(
        self,
        decl,
        typedefs_by_id: dict[str, Typedef],
        typedefs_by_name: dict[str, Typedef],
    ):
        if isinstance(decl, Struct):
            return Struct(
                decl_id=decl.decl_id,
                name=decl.name,
                c_name=decl.c_name,
                fields=[
                    field.__class__(
                        name=field.name,
                        source_name=field.source_name,
                        type=self._normalize_type(field.type, typedefs_by_id, typedefs_by_name, set()),
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
        if isinstance(decl, Typedef):
            normalized_aliased = self._normalize_type(
                decl.aliased, typedefs_by_id, typedefs_by_name, {decl.decl_id}
            )
            normalized_canonical = self._canonicalize_type(
                normalized_aliased, typedefs_by_id, typedefs_by_name, {decl.decl_id}
            )
            return Typedef(
                decl_id=decl.decl_id,
                name=decl.name,
                aliased=normalized_aliased,
                canonical=normalized_canonical,
            )
        if isinstance(decl, Function):
            return Function(
                decl_id=decl.decl_id,
                name=decl.name,
                link_name=decl.link_name,
                ret=self._normalize_type(decl.ret, typedefs_by_id, typedefs_by_name, set()),
                params=[
                    param.__class__(
                        name=param.name,
                        type=self._normalize_type(param.type, typedefs_by_id, typedefs_by_name, set()),
                    )
                    for param in decl.params
                ],
                is_variadic=decl.is_variadic,
                calling_convention=decl.calling_convention,
                is_noreturn=decl.is_noreturn,
            )
        if isinstance(decl, GlobalVar):
            return GlobalVar(
                decl_id=decl.decl_id,
                name=decl.name,
                link_name=decl.link_name,
                type=self._normalize_type(decl.type, typedefs_by_id, typedefs_by_name, set()),
                is_const=decl.is_const,
                initializer=self._normalize_const_expr(
                    decl.initializer, typedefs_by_id, typedefs_by_name
                ),
            )
        if isinstance(decl, Const):
            return Const(
                name=decl.name,
                type=self._normalize_type(decl.type, typedefs_by_id, typedefs_by_name, set()),
                expr=self._normalize_const_expr(decl.expr, typedefs_by_id, typedefs_by_name),
            )
        if isinstance(decl, MacroDecl):
            return MacroDecl(
                name=decl.name,
                tokens=list(decl.tokens),
                kind=decl.kind,
                expr=self._normalize_const_expr(decl.expr, typedefs_by_id, typedefs_by_name),
                type=None
                if decl.type is None
                else self._normalize_type(decl.type, typedefs_by_id, typedefs_by_name, set()),
                diagnostic=decl.diagnostic,
            )
        if isinstance(decl, Enum):
            return Enum(
                decl_id=decl.decl_id,
                name=decl.name,
                c_name=decl.c_name,
                underlying=decl.underlying,
                enumerants=list(decl.enumerants),
            )
        return decl

    def _normalize_const_expr(
        self,
        expr,
        typedefs_by_id: dict[str, Typedef],
        typedefs_by_name: dict[str, Typedef],
    ):
        if expr is None:
            return None
        if isinstance(expr, CastExpr):
            return CastExpr(
                target=self._normalize_type(expr.target, typedefs_by_id, typedefs_by_name, set()),
                expr=self._normalize_const_expr(expr.expr, typedefs_by_id, typedefs_by_name),
            )
        if isinstance(expr, SizeOfExpr):
            return SizeOfExpr(
                target=self._normalize_type(expr.target, typedefs_by_id, typedefs_by_name, set())
            )
        if hasattr(expr, "operand"):
            return expr.__class__(
                op=expr.op,
                operand=self._normalize_const_expr(expr.operand, typedefs_by_id, typedefs_by_name),
            )
        if hasattr(expr, "lhs") and hasattr(expr, "rhs"):
            return expr.__class__(
                op=expr.op,
                lhs=self._normalize_const_expr(expr.lhs, typedefs_by_id, typedefs_by_name),
                rhs=self._normalize_const_expr(expr.rhs, typedefs_by_id, typedefs_by_name),
            )
        return expr

    def _normalize_type(
        self,
        t: Type,
        typedefs_by_id: dict[str, Typedef],
        typedefs_by_name: dict[str, Typedef],
        visiting: set[str],
    ) -> Type:
        if isinstance(t, QualifiedType):
            return QualifiedType(
                unqualified=self._normalize_type(
                    t.unqualified, typedefs_by_id, typedefs_by_name, visiting
                ),
                qualifiers=t.qualifiers,
            )
        if isinstance(t, AtomicType):
            return AtomicType(
                value_type=self._normalize_type(t.value_type, typedefs_by_id, typedefs_by_name, visiting)
            )
        if isinstance(t, Pointer):
            return Pointer(
                pointee=None
                if t.pointee is None
                else self._normalize_type(t.pointee, typedefs_by_id, typedefs_by_name, visiting)
            )
        if isinstance(t, Array):
            return Array(
                element=self._normalize_type(t.element, typedefs_by_id, typedefs_by_name, visiting),
                size=t.size,
                array_kind=t.array_kind,
            )
        if isinstance(t, FunctionPtr):
            return FunctionPtr(
                ret=self._normalize_type(t.ret, typedefs_by_id, typedefs_by_name, visiting),
                params=[
                    self._normalize_type(param, typedefs_by_id, typedefs_by_name, visiting)
                    for param in t.params
                ],
                param_names=None if t.param_names is None else list(t.param_names),
                is_variadic=t.is_variadic,
                calling_convention=t.calling_convention,
                is_noreturn=t.is_noreturn,
            )
        if isinstance(t, TypeRef):
            canonical = self._canonicalize_type(t, typedefs_by_id, typedefs_by_name, visiting)
            return TypeRef(decl_id=t.decl_id, name=t.name, canonical=canonical)
        return t

    def _canonicalize_type(
        self,
        t: Type,
        typedefs_by_id: dict[str, Typedef],
        typedefs_by_name: dict[str, Typedef],
        visiting: set[str],
    ) -> Type:
        if isinstance(t, TypeRef):
            target = None
            if t.decl_id:
                target = typedefs_by_id.get(t.decl_id)
            if target is None and t.name:
                target = typedefs_by_name.get(t.name)
            if target is None:
                return self._normalize_type(t.canonical, typedefs_by_id, typedefs_by_name, visiting)
            if target.decl_id in visiting:
                return self._normalize_type(target.canonical, typedefs_by_id, typedefs_by_name, visiting)
            return self._canonicalize_type(
                target.aliased,
                typedefs_by_id,
                typedefs_by_name,
                visiting | {target.decl_id},
            )
        return self._normalize_type(t, typedefs_by_id, typedefs_by_name, visiting)

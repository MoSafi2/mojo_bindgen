"""Clang type to IR type lowering.

This module owns `cx.Type -> ir.Type` conversion. It may consult declaration
index lookups, diagnostics, primitive typing, and record lowering helpers, but
it does not assemble top-level declarations or iterate source cursors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum as PyEnum, auto
from typing import Callable

import clang.cindex as cx

from mojo_bindgen.ir import (
    Array,
    ArrayKind,
    ComplexType,
    EnumRef,
    FunctionPtr,
    Pointer,
    Primitive,
    PrimitiveKind,
    Qualifiers,
    Type,
    TypeRef,
    UnsupportedType,
    VectorType,
)
from mojo_bindgen.parsing.compat import ClangCompat
from mojo_bindgen.parsing.interfaces import DeclarationIndex, DiagnosticSink, RecordTypeResolving
from mojo_bindgen.parsing.lowering.primitive import PrimitiveResolver, default_signed_int_primitive


class TypeContext(PyEnum):
    FIELD = auto()
    PARAM = auto()
    RETURN = auto()
    TYPEDEF = auto()


@dataclass
class TypeLowerer:
    """Lower clang types into IR types through explicit collaborators."""

    index: DeclarationIndex
    diagnostics: DiagnosticSink
    primitive_resolver: PrimitiveResolver
    record_types: RecordTypeResolving
    compat: ClangCompat = field(default_factory=ClangCompat)
    _dispatch_by_kind: dict[object, Callable[[cx.Type, TypeContext], Type]] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._dispatch_by_kind = self._build_type_dispatch()

    def lower(self, clang_type: cx.Type, ctx: TypeContext) -> Type:
        """Lower a clang type in the given semantic context."""
        t = self._normalize(clang_type)
        return self._lower(t, ctx)

    def _normalize(self, t: cx.Type) -> cx.Type:
        if t.kind == cx.TypeKind.ELABORATED:
            return self._normalize(t.get_named_type())
        return t

    def _lower(self, t: cx.Type, ctx: TypeContext) -> Type:
        handler = self._dispatch_by_kind.get(t.kind)
        if handler is not None:
            return handler(t, ctx)
        return self._lower_primitive(t)

    @staticmethod
    def _qualifiers(t: cx.Type) -> Qualifiers:
        return Qualifiers(
            is_const=t.is_const_qualified(),
            is_volatile=t.is_volatile_qualified(),
            is_restrict=t.is_restrict_qualified(),
        )

    @staticmethod
    def _array_kind(t: cx.Type, ctx: TypeContext) -> ArrayKind:
        if t.kind == cx.TypeKind.CONSTANTARRAY:
            return "fixed"
        if t.kind == cx.TypeKind.INCOMPLETEARRAY:
            return "flexible" if ctx == TypeContext.FIELD else "incomplete"
        if t.kind in (cx.TypeKind.VARIABLEARRAY, cx.TypeKind.DEPENDENTSIZEDARRAY):
            return "variable"
        return "incomplete"

    def _build_type_dispatch(self) -> dict[object, Callable[[cx.Type, TypeContext], Type]]:
        dispatch: dict[object, Callable[[cx.Type, TypeContext], Type]] = {
            cx.TypeKind.INVALID: self._lower_invalid,
            cx.TypeKind.UNEXPOSED: self._lower_unexposed,
            cx.TypeKind.TYPEDEF: self._lower_typedef,
            cx.TypeKind.VOID: self._lower_void,
            cx.TypeKind.POINTER: self._lower_pointer,
            cx.TypeKind.CONSTANTARRAY: self._lower_constant_array,
            cx.TypeKind.INCOMPLETEARRAY: self._lower_unsized_array,
            cx.TypeKind.VARIABLEARRAY: self._lower_unsized_array,
            cx.TypeKind.DEPENDENTSIZEDARRAY: self._lower_unsized_array,
            cx.TypeKind.RECORD: self._lower_record_with_ctx,
            cx.TypeKind.ENUM: self._lower_enum_with_ctx,
            cx.TypeKind.FUNCTIONPROTO: self._lower_fnptr,
            cx.TypeKind.FUNCTIONNOPROTO: self._lower_fnptr,
        }
        complex_kind = getattr(cx.TypeKind, "COMPLEX", None)
        if complex_kind is not None:
            dispatch[complex_kind] = self._lower_complex_with_ctx
        vector_kind = getattr(cx.TypeKind, "VECTOR", None)
        if vector_kind is not None:
            dispatch[vector_kind] = self._lower_vector_type
        ext_vector_kind = getattr(cx.TypeKind, "EXTVECTOR", None)
        if ext_vector_kind is not None:
            dispatch[ext_vector_kind] = self._lower_ext_vector_type
        return dispatch


    def _lower_invalid(self, t: cx.Type, _ctx: TypeContext) -> Type:
        self.diagnostics.add_type_diag("warning", t, "invalid type (INVALID)")
        return UnsupportedType(
            category="invalid",
            spelling=t.spelling or "invalid",
            reason="clang reported INVALID type kind",
        )

    def _lower_unexposed(self, t: cx.Type, _ctx: TypeContext) -> Type:
        self.diagnostics.add_type_diag("warning", t, "unexposed type (UNEXPOSED)")
        return UnsupportedType(
            category="unexposed",
            spelling=t.spelling or "unexposed",
            reason="clang reported UNEXPOSED type kind",
            size_bytes=max(0, t.get_size()) or None,
            align_bytes=max(0, t.get_align()) or None,
        )

    def _lower_void(self, _t: cx.Type, _ctx: TypeContext) -> Type:
        return Primitive(name="void", kind=PrimitiveKind.VOID, is_signed=False, size_bytes=0)

    def _lower_constant_array(self, t: cx.Type, ctx: TypeContext) -> Type:
        return self._lower_array(t, sized=True, ctx=ctx)

    def _lower_unsized_array(self, t: cx.Type, ctx: TypeContext) -> Type:
        return self._lower_array(t, sized=False, ctx=ctx)

    def _lower_record_with_ctx(self, t: cx.Type, _ctx: TypeContext) -> Type:
        return self._lower_record(t)

    def _lower_enum_with_ctx(self, t: cx.Type, _ctx: TypeContext) -> Type:
        return self._lower_enum(t)

    def _lower_complex_with_ctx(self, t: cx.Type, _ctx: TypeContext) -> Type:
        return self._lower_complex(t)

    def _lower_vector_type(self, t: cx.Type, _ctx: TypeContext) -> Type:
        return self._lower_vector(t, is_ext_vector=False)

    def _lower_ext_vector_type(self, t: cx.Type, _ctx: TypeContext) -> Type:
        return self._lower_vector(t, is_ext_vector=True)

    def _lower_typedef(self, t: cx.Type, ctx: TypeContext) -> Type:
        decl = t.get_declaration()
        name = decl.spelling or t.spelling
        canonical = self.lower(t.get_canonical(), ctx)
        if ctx in (TypeContext.PARAM, TypeContext.RETURN, TypeContext.TYPEDEF):
            return TypeRef(
                decl_id=self.index.decl_id_for_cursor(decl),
                name=name,
                canonical=canonical,
            )
        return canonical

    def _lower_pointer(self, t: cx.Type, ctx: TypeContext) -> Type:
        raw_pointee = t.get_pointee()
        qualifiers = self._qualifiers(raw_pointee)
        pointee = self._normalize(raw_pointee)
        if pointee.kind == cx.TypeKind.VOID:
            return Pointer(pointee=None, qualifiers=qualifiers)
        canonical_pointee = self._normalize(pointee.get_canonical())
        if canonical_pointee.kind in (cx.TypeKind.FUNCTIONPROTO, cx.TypeKind.FUNCTIONNOPROTO):
            return self._lower_fnptr(canonical_pointee, ctx)
        return Pointer(pointee=self.lower(pointee, ctx), qualifiers=qualifiers)

    def _lower_array(self, t: cx.Type, *, sized: bool, ctx: TypeContext) -> Type:
        element = self.lower(t.get_array_element_type(), ctx)
        size = t.get_array_size() if sized else None
        return Array(element=element, size=size, array_kind=self._array_kind(t, ctx))

    def _lower_record(self, t: cx.Type) -> Type:
        return self.record_types.lower_record_type(t)

    def _lower_enum(self, t: cx.Type) -> Type:
        decl = t.get_declaration()
        name = decl.spelling
        underlying = self.primitive_resolver.resolve_primitive(decl.enum_type)
        if name and underlying is not None:
            return EnumRef(
                decl_id=self.index.decl_id_for_cursor(decl),
                name=name,
                c_name=name,
                underlying=underlying,
            )
        if underlying is not None:
            return underlying
        return default_signed_int_primitive()

    def _lower_fnptr(self, t: cx.Type, ctx: TypeContext) -> FunctionPtr:
        ret = self.lower(t.get_result(), ctx)
        params: list[Type] = []
        is_variadic = False
        if t.kind == cx.TypeKind.FUNCTIONPROTO:
            for arg in t.argument_types():
                params.append(self.lower(arg, ctx))
            is_variadic = t.is_function_variadic()
        return FunctionPtr(
            ret=ret,
            params=params,
            is_variadic=is_variadic,
            calling_convention=self.compat.get_calling_convention(t),
        )

    def _lower_complex(self, t: cx.Type) -> Type:
        element = self.primitive_resolver.resolve_primitive(self.compat.get_element_type(t))
        if element is None:
            return UnsupportedType(
                category="complex",
                spelling=t.spelling or "complex",
                reason="complex element type is not a primitive scalar",
                size_bytes=max(0, t.get_size()) or None,
                align_bytes=max(0, t.get_align()) or None,
            )
        return ComplexType(element=element, size_bytes=max(0, t.get_size()))

    def _lower_vector(self, t: cx.Type, *, is_ext_vector: bool) -> Type:
        element = self.lower(self.compat.get_element_type(t), TypeContext.FIELD)
        return VectorType(
            element=element,
            count=self.compat.get_num_elements(t),
            size_bytes=max(0, t.get_size()),
            is_ext_vector=is_ext_vector,
        )

    def _lower_primitive(self, t: cx.Type) -> Type:
        prim = self.primitive_resolver.resolve_primitive(t)
        if prim is not None:
            return prim
        return UnsupportedType(
            category="unknown",
            spelling=t.spelling or "unknown",
            reason="type is neither scalar nor otherwise modeled",
            size_bytes=max(0, t.get_size()) or None,
            align_bytes=max(0, t.get_align()) or None,
        )

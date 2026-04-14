"""Clang type to IR type lowering.

This module owns `cx.Type -> ir.Type` conversion. It may consult declaration
index lookups, diagnostics, primitive typing, and record lowering helpers, but
it does not assemble top-level declarations or iterate source cursors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum as PyEnum, auto

import clang.cindex as cx

from mojo_bindgen.ir import (
    Array,
    ArrayKind,
    ComplexType,
    EnumRef,
    FunctionPtr,
    OpaqueRecordRef,
    Pointer,
    Primitive,
    PrimitiveKind,
    Qualifiers,
    Struct,
    StructRef,
    Type,
    TypeRef,
    UnsupportedType,
    VectorType,
)
from mojo_bindgen.parsing.compat import ClangCompat
from mojo_bindgen.parsing.interfaces import DeclarationIndex, DiagnosticSink, RecordLowering
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
    compat: ClangCompat = field(default_factory=ClangCompat)
    record_cache_by_decl_id: dict[str, Struct] = field(default_factory=dict)
    _record_lowerer: RecordLowering | None = None

    def bind_record_lowerer(self, record_lowerer: RecordLowering) -> None:
        """Attach the record lowerer used for record type definitions."""
        self._record_lowerer = record_lowerer

    def lower(self, clang_type: cx.Type, ctx: TypeContext) -> Type:
        """Lower a clang type in the given semantic context."""
        t = self._normalize(clang_type)
        return self._lower(t, ctx)

    def make_struct_ref(self, struct: Struct) -> StructRef:
        """Build a stable StructRef from one lowered Struct."""
        return StructRef(
            decl_id=struct.decl_id,
            name=struct.name,
            c_name=struct.c_name,
            is_union=struct.is_union,
            size_bytes=struct.size_bytes,
            is_anonymous=struct.is_anonymous,
        )

    def _normalize(self, t: cx.Type) -> cx.Type:
        if t.kind == cx.TypeKind.ELABORATED:
            return self._normalize(t.get_named_type())
        return t

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

    def _lower(self, t: cx.Type, ctx: TypeContext) -> Type:
        tk = t.kind

        if tk == cx.TypeKind.INVALID:
            self.diagnostics.add_type_diag("warning", t, "invalid type (INVALID)")
            return UnsupportedType(
                category="invalid",
                spelling=t.spelling or "invalid",
                reason="clang reported INVALID type kind",
            )
        if tk == cx.TypeKind.UNEXPOSED:
            self.diagnostics.add_type_diag("warning", t, "unexposed type (UNEXPOSED)")
            return UnsupportedType(
                category="unexposed",
                spelling=t.spelling or "unexposed",
                reason="clang reported UNEXPOSED type kind",
                size_bytes=max(0, t.get_size()) or None,
                align_bytes=max(0, t.get_align()) or None,
            )
        if tk == getattr(cx.TypeKind, "COMPLEX", object()):
            return self._lower_complex(t)
        if tk in (
            getattr(cx.TypeKind, "VECTOR", object()),
            getattr(cx.TypeKind, "EXTVECTOR", object()),
        ):
            return self._lower_vector(
                t,
                is_ext_vector=(tk == getattr(cx.TypeKind, "EXTVECTOR", object())),
            )
        if tk == cx.TypeKind.TYPEDEF:
            return self._lower_typedef(t, ctx)
        if tk == cx.TypeKind.VOID:
            return Primitive(name="void", kind=PrimitiveKind.VOID, is_signed=False, size_bytes=0)
        if tk == cx.TypeKind.POINTER:
            return self._lower_pointer(t, ctx)
        if tk == cx.TypeKind.CONSTANTARRAY:
            return self._lower_array(t, sized=True, ctx=ctx)
        if tk in (
            cx.TypeKind.INCOMPLETEARRAY,
            cx.TypeKind.VARIABLEARRAY,
            cx.TypeKind.DEPENDENTSIZEDARRAY,
        ):
            return self._lower_array(t, sized=False, ctx=ctx)
        if tk == cx.TypeKind.RECORD:
            return self._lower_record(t)
        if tk == cx.TypeKind.ENUM:
            return self._lower_enum(t)
        if tk in (cx.TypeKind.FUNCTIONPROTO, cx.TypeKind.FUNCTIONNOPROTO):
            return self._lower_fnptr(t, ctx)
        return self._lower_primitive(t)

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

    def _require_record_lowerer(self) -> RecordLowering:
        if self._record_lowerer is None:
            raise RuntimeError("TypeLowerer record lowerer has not been bound")
        return self._record_lowerer

    def _lower_record(self, t: cx.Type) -> Type:
        decl = t.get_declaration()
        decl_id = self.index.decl_id_for_cursor(decl)

        cached = self.record_cache_by_decl_id.get(decl_id)
        if cached is not None:
            return self.make_struct_ref(cached)

        definition = self.index.record_definition_for_cursor(decl)
        if definition is not None:
            if decl.spelling and decl_id in self.index.top_level_decl_ids:
                return StructRef(
                    decl_id=decl_id,
                    name=decl.spelling,
                    c_name=decl.spelling,
                    is_union=(definition.kind == cx.CursorKind.UNION_DECL),
                    size_bytes=max(0, t.get_size()),
                    is_anonymous=False,
                )
            _, struct = self._require_record_lowerer().lower_record_definition(definition)
            return self.make_struct_ref(struct)

        if decl.spelling:
            return OpaqueRecordRef(
                decl_id=decl_id,
                name=decl.spelling,
                c_name=decl.spelling,
                is_union=(decl.kind == cx.CursorKind.UNION_DECL),
            )
        return UnsupportedType(
            category="unsupported_extension",
            spelling="__anonymous_record",
            reason="anonymous incomplete record reference cannot be named",
        )

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

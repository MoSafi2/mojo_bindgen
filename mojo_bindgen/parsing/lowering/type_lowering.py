from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum as PyEnum, auto
from typing import Callable

import clang.cindex as cx

from mojo_bindgen.ir import (
    AtomicType,
    Array,
    ComplexType,
    EnumRef,
    FloatType,
    FunctionPtr,
    Pointer,
    Qualifiers,
    QualifiedType,
    Type,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)
from mojo_bindgen.parsing.frontend import ClangCompat
from mojo_bindgen.parsing.diagnostics import ParserDiagnosticSink
from mojo_bindgen.parsing.index import DeclIndex
from mojo_bindgen.parsing.lowering.primitive import (
    PrimitiveResolver,
    default_signed_int_primitive,
)
from mojo_bindgen.parsing.lowering.record_types import RecordTypeResolver


class TypeContext(PyEnum):
    FIELD = auto()
    PARAM = auto()
    RETURN = auto()
    TYPEDEF = auto()


_TYPEREF_CONTEXTS = {TypeContext.PARAM, TypeContext.RETURN, TypeContext.TYPEDEF}


@dataclass
class TypeLowerer:
    index: DeclIndex
    diagnostics: ParserDiagnosticSink
    primitive_resolver: PrimitiveResolver
    record_types: RecordTypeResolver
    compat: ClangCompat = field(default_factory=ClangCompat)
    _dispatch_by_kind: dict[object, Callable[[cx.Type, TypeContext], Type]] = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._dispatch_by_kind = self._build_type_dispatch()

    def lower(self, clang_type: cx.Type, ctx: TypeContext) -> Type:
        t = self._normalize(clang_type)
        handler = self._dispatch_by_kind.get(t.kind)
        if handler is not None:
            return handler(t, ctx)
        return self._lower_primitive(t)

    def _build_type_dispatch(
        self,
    ) -> dict[object, Callable[[cx.Type, TypeContext], Type]]:
        dispatch: dict[object, Callable[[cx.Type, TypeContext], Type]] = {
            cx.TypeKind.INVALID: self._lower_invalid,
            cx.TypeKind.UNEXPOSED: self._lower_unexposed,
            cx.TypeKind.TYPEDEF: self._lower_typedef,
            cx.TypeKind.VOID: self._lower_void,
            cx.TypeKind.POINTER: self._lower_pointer,
            cx.TypeKind.CONSTANTARRAY: self._lower_array,
            cx.TypeKind.INCOMPLETEARRAY: self._lower_array,
            cx.TypeKind.VARIABLEARRAY: self._lower_array,
            cx.TypeKind.DEPENDENTSIZEDARRAY: self._lower_array,
            cx.TypeKind.RECORD: lambda t, _ctx: self._lower_record(t),
            cx.TypeKind.ENUM: lambda t, _ctx: self._lower_enum(t),
            cx.TypeKind.FUNCTIONPROTO: self._lower_fnptr,
            cx.TypeKind.FUNCTIONNOPROTO: self._lower_fnptr,
        }
        if (complex_kind := getattr(cx.TypeKind, "COMPLEX", None)) is not None:
            dispatch[complex_kind] = lambda t, _ctx: self._lower_complex(t)
        if (vector_kind := getattr(cx.TypeKind, "VECTOR", None)) is not None:
            dispatch[vector_kind] = lambda t, _ctx: self._lower_vector(
                t, is_ext_vector=False
            )
        if (ext_vector_kind := getattr(cx.TypeKind, "EXTVECTOR", None)) is not None:
            dispatch[ext_vector_kind] = lambda t, _ctx: self._lower_vector(
                t, is_ext_vector=True
            )
        if (atomic_kind := getattr(cx.TypeKind, "ATOMIC", None)) is not None:
            dispatch[atomic_kind] = self._lower_atomic
        return dispatch

    @staticmethod
    def _normalize(t: cx.Type) -> cx.Type:
        if t.kind == cx.TypeKind.ELABORATED:
            return TypeLowerer._normalize(t.get_named_type())
        return t

    @staticmethod
    def _qualifiers(t: cx.Type) -> Qualifiers:
        return Qualifiers(
            is_const=t.is_const_qualified(),
            is_volatile=t.is_volatile_qualified(),
            is_restrict=t.is_restrict_qualified(),
        )

    @staticmethod
    def _safe_size(t: cx.Type) -> int | None:
        return max(0, t.get_size()) or None

    @staticmethod
    def _safe_align(t: cx.Type) -> int | None:
        return max(0, t.get_align()) or None

    @staticmethod
    def _array_kind(t: cx.Type, ctx: TypeContext) -> str:
        if t.kind == cx.TypeKind.CONSTANTARRAY:
            return "fixed"
        if t.kind == cx.TypeKind.INCOMPLETEARRAY:
            return "flexible" if ctx == TypeContext.FIELD else "incomplete"
        if t.kind in (cx.TypeKind.VARIABLEARRAY, cx.TypeKind.DEPENDENTSIZEDARRAY):
            return "variable"
        return "incomplete"

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
            size_bytes=self._safe_size(t),
            align_bytes=self._safe_align(t),
        )

    def _lower_void(self, _t: cx.Type, _ctx: TypeContext) -> Type:
        return VoidType()

    def _lower_typedef(self, t: cx.Type, ctx: TypeContext) -> Type:
        decl = t.get_declaration()
        name = decl.spelling or t.spelling
        canonical = self.lower(t.get_canonical(), ctx)
        if ctx in _TYPEREF_CONTEXTS:
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
            if qualifiers == Qualifiers():
                return Pointer(pointee=None)
            return Pointer(pointee=QualifiedType(unqualified=VoidType(), qualifiers=qualifiers))
        canonical_pointee = self._normalize(pointee.get_canonical())
        if canonical_pointee.kind in (
            cx.TypeKind.FUNCTIONPROTO,
            cx.TypeKind.FUNCTIONNOPROTO,
        ):
            return self._lower_fnptr(canonical_pointee, ctx)
        lowered = self.lower(pointee, ctx)
        if qualifiers != Qualifiers():
            lowered = QualifiedType(unqualified=lowered, qualifiers=qualifiers)
        return Pointer(pointee=lowered)

    def _lower_array(self, t: cx.Type, ctx: TypeContext) -> Type:
        element = self.lower(t.get_array_element_type(), ctx)
        size = t.get_array_size() if t.kind == cx.TypeKind.CONSTANTARRAY else None
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
        params = (
            [self.lower(arg, ctx) for arg in t.argument_types()]
            if t.kind == cx.TypeKind.FUNCTIONPROTO
            else []
        )
        is_variadic = (
            t.is_function_variadic() if t.kind == cx.TypeKind.FUNCTIONPROTO else False
        )
        return FunctionPtr(
            ret=ret,
            params=params,
            is_variadic=is_variadic,
            calling_convention=self.compat.get_calling_convention(t),
        )

    def _lower_complex(self, t: cx.Type) -> Type:
        element = self.primitive_resolver.resolve_primitive(
            self.compat.get_element_type(t)
        )
        if not isinstance(element, FloatType):
            return UnsupportedType(
                category="complex",
                spelling=t.spelling or "complex",
                reason="complex element type is not a primitive scalar",
                size_bytes=self._safe_size(t),
                align_bytes=self._safe_align(t),
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

    def _lower_atomic(self, t: cx.Type, ctx: TypeContext) -> Type:
        inner = self._lower_atomic_value_type(t, ctx)
        self.diagnostics.add_type_diag(
            "warning",
            t,
            "atomic semantics are preserved in IR but erased in generated Mojo",
        )
        return AtomicType(value_type=inner)

    def _lower_atomic_value_type(self, t: cx.Type, ctx: TypeContext) -> Type:
        spelling = t.spelling.strip()
        if spelling.startswith("_Atomic(") and spelling.endswith(")"):
            inner_spelling = spelling[len("_Atomic(") : -1].strip()
        elif spelling.startswith("_Atomic "):
            inner_spelling = spelling[len("_Atomic ") :].strip()
        else:
            return UnsupportedType(
                category="unsupported_extension",
                spelling=spelling or "_Atomic",
                reason="unable to recover atomic value type from clang spelling",
                size_bytes=self._safe_size(t),
                align_bytes=self._safe_align(t),
            )

        idx = cx.Index.create()
        src = f"{inner_spelling} __bindgen_atomic_inner;\n"
        tu = idx.parse(
            "__bindgen_atomic_inner.c",
            args=self.primitive_resolver.compile_args,
            unsaved_files=[("__bindgen_atomic_inner.c", src)],
            options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        for cursor in tu.cursor.get_children():
            if cursor.kind == cx.CursorKind.VAR_DECL and cursor.spelling == "__bindgen_atomic_inner":
                return self.lower(cursor.type, ctx)
        return UnsupportedType(
            category="unsupported_extension",
            spelling=spelling or "_Atomic",
            reason="failed to parse atomic value type from recovered spelling",
            size_bytes=self._safe_size(t),
            align_bytes=self._safe_align(t),
        )

    def _lower_primitive(self, t: cx.Type) -> Type:
        prim = self.primitive_resolver.resolve_primitive(t)
        if prim is not None:
            return prim
        return UnsupportedType(
            category="unknown",
            spelling=t.spelling or "unknown",
            reason="type is neither scalar nor otherwise modeled",
            size_bytes=self._safe_size(t),
            align_bytes=self._safe_align(t),
        )

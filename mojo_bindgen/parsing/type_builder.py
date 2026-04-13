"""Policy-aware clang.Type -> IR Type lowering."""

from __future__ import annotations

from enum import Enum, auto
import hashlib

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
    StructRef,
    Type,
    TypeRef,
    UnsupportedType,
    VectorType,
)
from mojo_bindgen.parsing.type_resolver import TypeResolver


class TypeContext(Enum):
    FIELD = auto()
    PARAM = auto()
    RETURN = auto()
    TYPEDEF = auto()


class TypeBuilder:
    def __init__(self, resolver: TypeResolver) -> None:
        self.resolver = resolver

    def build(self, clang_type: cx.Type, ctx: TypeContext) -> Type:
        t = self._normalize(clang_type)
        return self._lower(t, ctx)

    def _normalize(self, t: cx.Type) -> cx.Type:
        if t.kind == cx.TypeKind.ELABORATED:
            return self._normalize(t.get_named_type())
        return t

    @staticmethod
    def _decl_id_for_cursor(cursor: cx.Cursor) -> str:
        usr = cursor.get_usr()
        if usr:
            return usr
        loc = cursor.location
        loc_key = f"{loc.file}:{loc.line}:{loc.column}:{cursor.kind}:{cursor.spelling}"
        digest = hashlib.sha256(loc_key.encode("utf-8")).hexdigest()[:16]
        return f"anon:{digest}"

    @staticmethod
    def _qualifiers(t: cx.Type) -> Qualifiers:
        return Qualifiers(
            is_const=t.is_const_qualified(),
            is_volatile=t.is_volatile_qualified(),
            is_restrict=t.is_restrict_qualified(),
        )

    @staticmethod
    def _calling_convention(t: cx.Type) -> str | None:
        if hasattr(t, "get_canonical"):
            t = t.get_canonical()
        getter = getattr(t, "get_calling_conv", None)
        if getter is None:
            getter = getattr(t, "calling_conv", None)
        if getter is None:
            return None
        try:
            value = getter() if callable(getter) else getter
        except Exception:
            return None
        if value is None:
            return None
        name = getattr(value, "name", None)
        if isinstance(name, str) and name:
            return name
        try:
            return str(value)
        except Exception:
            return None

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
            self.resolver._append_type_kind_warning(t, "invalid type (INVALID)")
            return UnsupportedType(
                category="invalid",
                spelling=t.spelling or "invalid",
                reason="clang reported INVALID type kind",
            )
        if tk == cx.TypeKind.UNEXPOSED:
            self.resolver._append_type_kind_warning(t, "unexposed type (UNEXPOSED)")
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
            return self._lower_vector(t, is_ext_vector=(tk == getattr(cx.TypeKind, "EXTVECTOR", object())))

        if tk == cx.TypeKind.TYPEDEF:
            return self._lower_typedef(t, ctx)
        if tk == cx.TypeKind.VOID:
            return Primitive(
                name="void",
                kind=PrimitiveKind.VOID,
                is_signed=False,
                size_bytes=0,
            )
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
        canonical = self.build(t.get_canonical(), ctx)
        if ctx in (TypeContext.PARAM, TypeContext.RETURN, TypeContext.TYPEDEF):
            return TypeRef(
                decl_id=self._decl_id_for_cursor(decl),
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
        if canonical_pointee.kind in (
            cx.TypeKind.FUNCTIONPROTO,
            cx.TypeKind.FUNCTIONNOPROTO,
        ):
            return self._lower_fnptr(canonical_pointee, ctx)

        return Pointer(pointee=self.build(pointee, ctx), qualifiers=qualifiers)

    def _lower_array(self, t: cx.Type, *, sized: bool, ctx: TypeContext) -> Type:
        element = self.build(t.get_array_element_type(), ctx)
        size = t.get_array_size() if sized else None
        return Array(element=element, size=size, array_kind=self._array_kind(t, ctx))

    def _make_struct_ref(
        self,
        decl_id: str,
        struct_name: str,
        c_name: str,
        is_union: bool,
        size_bytes: int,
        is_anonymous: bool,
    ) -> StructRef:
        return StructRef(
            decl_id=decl_id,
            name=struct_name,
            c_name=c_name,
            is_union=is_union,
            size_bytes=size_bytes,
            is_anonymous=is_anonymous,
        )

    def _lower_record(self, t: cx.Type) -> Type:
        decl = t.get_declaration()
        usr = decl.get_usr()
        c_name = decl.spelling

        if usr in self.resolver.type_cache:
            s = self.resolver.type_cache[usr]
            return self._make_struct_ref(
                s.decl_id, s.name, s.c_name, s.is_union, s.size_bytes, s.is_anonymous
            )

        # Break self-recursive record cycles (e.g. struct node { struct node* next; }).
        # Named definitions are emitted by top-level traversal, so we can return a ref
        # directly without recursively materializing the same definition here.
        if c_name and c_name in self.resolver.defined_structs:
            return self._make_struct_ref(
                decl_id=self._decl_id_for_cursor(decl),
                struct_name=c_name,
                c_name=c_name,
                is_union=(decl.kind == cx.CursorKind.UNION_DECL),
                size_bytes=max(0, t.get_size()),
                is_anonymous=False,
            )

        if decl.is_definition():
            s = self.resolver._build_struct(decl.get_definition(), None)
            if s is not None:
                self.resolver.type_cache[usr] = s
                return self._make_struct_ref(
                    s.decl_id, s.name, s.c_name, s.is_union, s.size_bytes, s.is_anonymous
                )

        if c_name:
            return OpaqueRecordRef(
                decl_id=self._decl_id_for_cursor(decl),
                name=c_name,
                c_name=c_name,
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
        decl_id = self._decl_id_for_cursor(decl)
        underlying = self.resolver.resolve_primitive(decl.enum_type)
        if name and underlying is not None:
            return EnumRef(decl_id=decl_id, name=name, c_name=name, underlying=underlying)
        if underlying is not None:
            return underlying
        return Primitive(
            name="int",
            kind=PrimitiveKind.INT,
            is_signed=True,
            size_bytes=4,
        )

    def _lower_fnptr(self, t: cx.Type, ctx: TypeContext) -> FunctionPtr:
        ret = self.build(t.get_result(), ctx)
        params: list[Type] = []
        is_variadic = False
        if t.kind == cx.TypeKind.FUNCTIONPROTO:
            for arg in t.argument_types():
                params.append(self.build(arg, ctx))
            is_variadic = t.is_function_variadic()
        return FunctionPtr(
            ret=ret,
            params=params,
            is_variadic=is_variadic,
            calling_convention=self._calling_convention(t),
        )

    def _lower_complex(self, t: cx.Type) -> Type:
        element_type = getattr(t, "get_element_type", None)
        if callable(element_type):
            inner = element_type()
        else:
            inner = getattr(t, "element_type")
        element = self.resolver.resolve_primitive(inner)
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
        element_type = getattr(t, "get_element_type", None)
        if callable(element_type):
            inner = element_type()
        else:
            inner = getattr(t, "element_type")
        element = self.build(inner, TypeContext.FIELD)
        count_getter = getattr(t, "get_num_elements", None)
        count: int | None = None
        if callable(count_getter):
            try:
                count = count_getter()
            except Exception:
                count = None
        return VectorType(
            element=element,
            count=count if isinstance(count, int) and count >= 0 else None,
            size_bytes=max(0, t.get_size()),
            is_ext_vector=is_ext_vector,
        )

    def _lower_primitive(self, t: cx.Type) -> Type:
        prim = self.resolver.resolve_primitive(t)
        if prim is not None:
            return prim
        return UnsupportedType(
            category="unknown",
            spelling=t.spelling or "unknown",
            reason="type is neither scalar nor otherwise modeled",
            size_bytes=max(0, t.get_size()) or None,
            align_bytes=max(0, t.get_align()) or None,
        )

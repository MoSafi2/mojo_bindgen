"""Policy-aware clang.Type -> IR Type lowering."""

from __future__ import annotations

from enum import Enum, auto

import clang.cindex as cx

from mojo_bindgen.ir import (
    Array,
    EnumRef,
    FunctionPtr,
    Opaque,
    Pointer,
    Primitive,
    PrimitiveKind,
    StructRef,
    Type,
    TypeRef,
)
from mojo_bindgen.type_resolver import TypeResolver


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

    def _lower(self, t: cx.Type, ctx: TypeContext) -> Type:
        tk = t.kind

        if tk == cx.TypeKind.INVALID:
            self.resolver._append_type_kind_warning(t, "invalid type (INVALID)")
            return Opaque(name="invalid")
        if tk == cx.TypeKind.UNEXPOSED:
            self.resolver._append_type_kind_warning(t, "unexposed type (UNEXPOSED)")
            return Opaque(name=t.spelling or "unexposed")

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
            return TypeRef(name=name, canonical=canonical)
        return canonical

    def _lower_pointer(self, t: cx.Type, ctx: TypeContext) -> Type:
        raw_pointee = t.get_pointee()
        is_const = raw_pointee.is_const_qualified()
        pointee = self._normalize(raw_pointee)

        if pointee.kind == cx.TypeKind.VOID:
            return Pointer(pointee=None, is_const=is_const)

        canonical_pointee = self._normalize(pointee.get_canonical())
        if canonical_pointee.kind in (
            cx.TypeKind.FUNCTIONPROTO,
            cx.TypeKind.FUNCTIONNOPROTO,
        ):
            return self._lower_fnptr(canonical_pointee, ctx)

        return Pointer(pointee=self.build(pointee, ctx), is_const=is_const)

    def _lower_array(self, t: cx.Type, *, sized: bool, ctx: TypeContext) -> Type:
        element = self.build(t.get_array_element_type(), ctx)
        size = t.get_array_size() if sized else None
        return Array(element=element, size=size)

    def _make_struct_ref(self, struct_name: str, c_name: str, is_union: bool, size_bytes: int) -> StructRef:
        return StructRef(
            name=struct_name,
            c_name=c_name,
            is_union=is_union,
            size_bytes=size_bytes,
        )

    def _lower_record(self, t: cx.Type) -> Type:
        decl = t.get_declaration()
        usr = decl.get_usr()
        c_name = decl.spelling

        if usr in self.resolver.type_cache:
            s = self.resolver.type_cache[usr]
            return self._make_struct_ref(s.name, s.c_name, s.is_union, s.size_bytes)

        # Break self-recursive record cycles (e.g. struct node { struct node* next; }).
        # Named definitions are emitted by top-level traversal, so we can return a ref
        # directly without recursively materializing the same definition here.
        if c_name and c_name in self.resolver.defined_structs:
            return self._make_struct_ref(
                struct_name=c_name,
                c_name=c_name,
                is_union=(decl.kind == cx.CursorKind.UNION_DECL),
                size_bytes=max(0, t.get_size()),
            )

        if decl.is_definition():
            s = self.resolver._build_struct(decl.get_definition(), None)
            if s is not None:
                self.resolver.type_cache[usr] = s
                return self._make_struct_ref(s.name, s.c_name, s.is_union, s.size_bytes)

        if c_name:
            return Opaque(name=c_name)
        return Opaque(name="__anonymous_record")

    def _lower_enum(self, t: cx.Type) -> Type:
        decl = t.get_declaration()
        name = decl.spelling
        underlying = self.resolver.resolve_primitive(decl.enum_type)
        if name and underlying is not None:
            return EnumRef(name=name, c_name=name, underlying=underlying)
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
        return FunctionPtr(ret=ret, params=params, is_variadic=is_variadic)

    def _lower_primitive(self, t: cx.Type) -> Type:
        prim = self.resolver.resolve_primitive(t)
        if prim is not None:
            return prim
        return Opaque(name=t.spelling or "unknown")

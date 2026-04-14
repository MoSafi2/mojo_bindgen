"""Shared clang-to-IR lowering services for the parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum as PyEnum, auto

import clang.cindex as cx

from mojo_bindgen.ir import (
    Array,
    ArrayKind,
    ComplexType,
    Const,
    Decl,
    Enum,
    EnumRef,
    Enumerant,
    Field,
    Function,
    FunctionPtr,
    GlobalVar,
    IRDiagnostic,
    IntLiteral,
    OpaqueRecordRef,
    Param,
    Pointer,
    Primitive,
    PrimitiveKind,
    Qualifiers,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Typedef,
    UnsupportedType,
    VectorType,
)
from mojo_bindgen.parsing.const_expr import ConstExprParser
from mojo_bindgen.parsing.frontend import ClangFrontend, FrontendDiagnostic
from mojo_bindgen.parsing.registry import DeclRegistry
from mojo_bindgen.utils import build_c_parse_args


@dataclass(frozen=True)
class BuiltinPrimitiveSpelling:
    """Kind metadata for canonical primitive C spellings."""

    kind: PrimitiveKind
    is_signed: bool = False


_PS_VOID = BuiltinPrimitiveSpelling(kind=PrimitiveKind.VOID)
_PS_BOOL = BuiltinPrimitiveSpelling(kind=PrimitiveKind.BOOL)
_PS_CHAR = BuiltinPrimitiveSpelling(kind=PrimitiveKind.CHAR)
_PS_SINT = BuiltinPrimitiveSpelling(kind=PrimitiveKind.INT, is_signed=True)
_PS_UINT = BuiltinPrimitiveSpelling(kind=PrimitiveKind.INT, is_signed=False)
_PS_FLOAT = BuiltinPrimitiveSpelling(kind=PrimitiveKind.FLOAT)

_PRIMITIVE_SPELLINGS: dict[str, BuiltinPrimitiveSpelling] = {
    "void": _PS_VOID,
    "_Bool": _PS_BOOL,
    "char": _PS_CHAR,
    "signed char": _PS_SINT,
    "unsigned char": _PS_UINT,
    "short": _PS_SINT,
    "short int": _PS_SINT,
    "signed short": _PS_SINT,
    "signed short int": _PS_SINT,
    "unsigned short": _PS_UINT,
    "unsigned short int": _PS_UINT,
    "int": _PS_SINT,
    "signed": _PS_SINT,
    "signed int": _PS_SINT,
    "unsigned": _PS_UINT,
    "unsigned int": _PS_UINT,
    "long": _PS_SINT,
    "long int": _PS_SINT,
    "signed long": _PS_SINT,
    "unsigned long": _PS_UINT,
    "unsigned long int": _PS_UINT,
    "long long": _PS_SINT,
    "long long int": _PS_SINT,
    "signed long long": _PS_SINT,
    "signed long long int": _PS_SINT,
    "unsigned long long": _PS_UINT,
    "unsigned long long int": _PS_UINT,
    "float": _PS_FLOAT,
    "double": _PS_FLOAT,
    "long double": _PS_FLOAT,
    "int8_t": _PS_SINT,
    "int16_t": _PS_SINT,
    "int32_t": _PS_SINT,
    "int64_t": _PS_SINT,
    "uint8_t": _PS_UINT,
    "uint16_t": _PS_UINT,
    "uint32_t": _PS_UINT,
    "uint64_t": _PS_UINT,
    "size_t": _PS_UINT,
    "ssize_t": _PS_SINT,
    "ptrdiff_t": _PS_SINT,
    "intptr_t": _PS_SINT,
    "uintptr_t": _PS_UINT,
}


def _c_integer_spelling_for_literal_suffix(suffix: str) -> str:
    """Map a C integer literal suffix to a canonical integer spelling."""
    if not suffix:
        return "int"
    s = suffix.lower()
    has_u = "u" in s
    l_count = s.count("l")
    if l_count >= 2:
        return "unsigned long long" if has_u else "long long"
    if l_count == 1:
        return "unsigned long" if has_u else "long"
    return "unsigned int" if has_u else "int"


_LITERAL_SUFFIX_PREWARM: frozenset[str] = frozenset(
    {
        "",
        "u",
        "U",
        "l",
        "L",
        "ll",
        "LL",
        "ul",
        "uL",
        "Ul",
        "UL",
        "lu",
        "lU",
        "Lu",
        "LU",
        "llu",
        "llU",
        "LLu",
        "LLU",
        "ull",
        "uLL",
        "Ull",
        "ULL",
    }
)


def _suffix_probe_parse_args(compile_args: list[str]) -> list[str]:
    """Build parse args for integer literal suffix type probes."""
    return build_c_parse_args(compile_args, default_std="-std=gnu11")


class TypeContext(PyEnum):
    FIELD = auto()
    PARAM = auto()
    RETURN = auto()
    TYPEDEF = auto()


@dataclass
class ClangCompat:
    """Compatibility helpers for libclang Python binding differences."""

    def get_calling_convention(self, t: cx.Type) -> str | None:
        """Return a readable calling-convention string if available."""
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

    def get_element_type(self, t: cx.Type) -> cx.Type:
        """Return a vector or complex element type across libclang variants."""
        getter = getattr(t, "get_element_type", None)
        if callable(getter):
            return getter()
        return getattr(t, "element_type")

    def get_num_elements(self, t: cx.Type) -> int | None:
        """Return vector element count across libclang variants."""
        getter = getattr(t, "get_num_elements", None)
        if not callable(getter):
            return None
        try:
            count = getter()
        except Exception:
            return None
        return count if isinstance(count, int) and count >= 0 else None


class PrimitiveResolver:
    """Primitive classification and integer-literal ABI probing."""

    def __init__(self, compile_args: list[str]) -> None:
        self.compile_args = list(compile_args)
        self._literal_suffix_cache: dict[str, Primitive] = {}
        for suffix in _LITERAL_SUFFIX_PREWARM:
            self.primitive_for_integer_literal_suffix(suffix)

    def primitive_for_integer_literal_suffix(self, suffix: str) -> Primitive:
        """Map an integer literal suffix to an ABI-correct primitive."""
        if suffix in self._literal_suffix_cache:
            return self._literal_suffix_cache[suffix]
        spelling = _c_integer_spelling_for_literal_suffix(suffix)
        idx = cx.Index.create()
        src = f"{spelling} __bindgen_m;\n"
        tu = idx.parse(
            "__bindgen_suffix_probe.c",
            args=_suffix_probe_parse_args(self.compile_args),
            unsaved_files=[("__bindgen_suffix_probe.c", src)],
            options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        prim: Primitive | None = None
        for cursor in tu.cursor.get_children():
            if cursor.kind == cx.CursorKind.VAR_DECL and cursor.spelling == "__bindgen_m":
                prim = self.make_primitive_from_kind(cursor.type)
                break
        if prim is None:
            prim = Primitive(
                name=spelling,
                kind=PrimitiveKind.INT,
                is_signed="unsigned" not in spelling.split(),
                size_bytes=4,
            )
        self._literal_suffix_cache[suffix] = prim
        return prim

    def make_primitive_from_kind(self, clang_type: cx.Type) -> Primitive:
        """Lower a scalar clang type to a primitive IR node."""
        canonical = clang_type.get_canonical()
        spelling = canonical.spelling
        norm = re.sub(r"\b(const|volatile|restrict)\b", "", spelling).strip()

        defaults = _PRIMITIVE_SPELLINGS.get(norm)
        if defaults:
            kind = defaults.kind
            if kind == PrimitiveKind.INT:
                is_signed = defaults.is_signed
            elif kind == PrimitiveKind.CHAR:
                is_signed = canonical.kind == cx.TypeKind.CHAR_S
            else:
                is_signed = False
        else:
            tk = canonical.kind
            if tk == cx.TypeKind.BOOL:
                kind = PrimitiveKind.BOOL
                is_signed = False
            elif tk in (
                cx.TypeKind.FLOAT,
                cx.TypeKind.DOUBLE,
                cx.TypeKind.LONGDOUBLE,
                cx.TypeKind.HALF,
            ):
                kind = PrimitiveKind.FLOAT
                is_signed = False
            elif tk in (cx.TypeKind.CHAR_S, cx.TypeKind.CHAR_U) and norm == "char":
                kind = PrimitiveKind.CHAR
                is_signed = tk == cx.TypeKind.CHAR_S
            else:
                kind = PrimitiveKind.INT
                is_signed = tk in (
                    cx.TypeKind.CHAR_S,
                    cx.TypeKind.SCHAR,
                    cx.TypeKind.SHORT,
                    cx.TypeKind.INT,
                    cx.TypeKind.LONG,
                    cx.TypeKind.LONGLONG,
                    cx.TypeKind.INT128,
                    cx.TypeKind.WCHAR,
                )

        size_raw = canonical.get_size()
        size_bytes = size_raw if size_raw > 0 else 0
        return Primitive(
            name=norm or spelling,
            kind=kind,
            is_signed=is_signed,
            size_bytes=size_bytes,
        )

    def resolve_primitive(self, clang_type: cx.Type) -> Primitive | None:
        """Return a primitive for scalar clang types, else ``None``."""
        canonical = clang_type.get_canonical()
        tk = canonical.kind
        scalar_kinds = {
            cx.TypeKind.BOOL,
            cx.TypeKind.CHAR_U, cx.TypeKind.UCHAR,
            cx.TypeKind.CHAR16, cx.TypeKind.CHAR32,
            cx.TypeKind.USHORT, cx.TypeKind.UINT,
            cx.TypeKind.ULONG, cx.TypeKind.ULONGLONG,
            cx.TypeKind.UINT128,
            cx.TypeKind.CHAR_S, cx.TypeKind.SCHAR,
            cx.TypeKind.WCHAR,
            cx.TypeKind.SHORT, cx.TypeKind.INT,
            cx.TypeKind.LONG, cx.TypeKind.LONGLONG,
            cx.TypeKind.INT128,
            cx.TypeKind.FLOAT,
            cx.TypeKind.DOUBLE,
            cx.TypeKind.LONGDOUBLE,
            cx.TypeKind.HALF,
        }
        if tk not in scalar_kinds:
            return None
        return self.make_primitive_from_kind(clang_type)


@dataclass
class LoweringContext:
    """Shared lowering state for one translation unit."""

    frontend: ClangFrontend
    registry: DeclRegistry
    tu: cx.TranslationUnit
    header: str
    library: str
    link_name: str
    diagnostics: list[FrontendDiagnostic]
    primitive_resolver: PrimitiveResolver
    compat: ClangCompat = field(default_factory=ClangCompat)
    record_cache_by_decl_id: dict[str, Struct] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.const_expr_parser = ConstExprParser(self.primitive_resolver)
        self.type_lowerer = TypeLowerer(self)
        self.record_lowerer = RecordLowerer(self)
        self.decl_lowerer = DeclLowerer(self)

    def append_diag(self, severity: str, cursor: cx.Cursor, message: str) -> None:
        """Append a normalized cursor-based diagnostic."""
        loc = cursor.location
        self.diagnostics.append(
            FrontendDiagnostic(
                severity=severity,
                file=loc.file.name if loc.file else "<unknown>",
                line=loc.line,
                col=loc.column,
                message=message,
            )
        )

    def append_type_kind_warning(self, clang_type: cx.Type, kind_label: str) -> None:
        """Append a type-based warning for unsupported clang kinds."""
        self.diagnostics.append(
            FrontendDiagnostic(
                severity="warning",
                file="<type>",
                line=0,
                col=0,
                message=f"{kind_label}: {clang_type.spelling!r}",
            )
        )

    def to_ir_diagnostics(self) -> list[IRDiagnostic]:
        """Convert accumulated frontend diagnostics to IR diagnostics."""
        return [
            IRDiagnostic(
                severity=d.severity,
                message=d.message,
                file=d.file,
                line=d.line,
                col=d.col,
            )
            for d in self.diagnostics
        ]


class TypeLowerer:
    """Lower clang types into IR types using the shared lowering context."""

    def __init__(self, context: LoweringContext) -> None:
        self.context = context

    def lower(self, clang_type: cx.Type, ctx: TypeContext) -> Type:
        """Lower a clang type in the given semantic context."""
        t = self._normalize(clang_type)
        return self._lower(t, ctx)

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
            self.context.append_type_kind_warning(t, "invalid type (INVALID)")
            return UnsupportedType(
                category="invalid",
                spelling=t.spelling or "invalid",
                reason="clang reported INVALID type kind",
            )
        if tk == cx.TypeKind.UNEXPOSED:
            self.context.append_type_kind_warning(t, "unexposed type (UNEXPOSED)")
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
                decl_id=self.context.registry.decl_id_for_cursor(decl),
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

    def _make_struct_ref(self, struct: Struct) -> StructRef:
        return StructRef(
            decl_id=struct.decl_id,
            name=struct.name,
            c_name=struct.c_name,
            is_union=struct.is_union,
            size_bytes=struct.size_bytes,
            is_anonymous=struct.is_anonymous,
        )

    def _lower_record(self, t: cx.Type) -> Type:
        decl = t.get_declaration()
        decl_id = self.context.registry.decl_id_for_cursor(decl)

        cached = self.context.record_cache_by_decl_id.get(decl_id)
        if cached is not None:
            return self._make_struct_ref(cached)

        definition = self.context.registry.record_definition_for_cursor(decl)
        if definition is not None:
            if decl.spelling and decl_id in self.context.registry.top_level_decl_ids:
                return StructRef(
                    decl_id=decl_id,
                    name=decl.spelling,
                    c_name=decl.spelling,
                    is_union=(definition.kind == cx.CursorKind.UNION_DECL),
                    size_bytes=max(0, t.get_size()),
                    is_anonymous=False,
                )
            _, struct = self.context.record_lowerer.lower_record_definition(definition)
            return self._make_struct_ref(struct)

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
        underlying = self.context.primitive_resolver.resolve_primitive(decl.enum_type)
        if name and underlying is not None:
            return EnumRef(
                decl_id=self.context.registry.decl_id_for_cursor(decl),
                name=name,
                c_name=name,
                underlying=underlying,
            )
        if underlying is not None:
            return underlying
        return Primitive(name="int", kind=PrimitiveKind.INT, is_signed=True, size_bytes=4)

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
            calling_convention=self.context.compat.get_calling_convention(t),
        )

    def _lower_complex(self, t: cx.Type) -> Type:
        element = self.context.primitive_resolver.resolve_primitive(
            self.context.compat.get_element_type(t)
        )
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
        element = self.lower(self.context.compat.get_element_type(t), TypeContext.FIELD)
        return VectorType(
            element=element,
            count=self.context.compat.get_num_elements(t),
            size_bytes=max(0, t.get_size()),
            is_ext_vector=is_ext_vector,
        )

    def _lower_primitive(self, t: cx.Type) -> Type:
        prim = self.context.primitive_resolver.resolve_primitive(t)
        if prim is not None:
            return prim
        return UnsupportedType(
            category="unknown",
            spelling=t.spelling or "unknown",
            reason="type is neither scalar nor otherwise modeled",
            size_bytes=max(0, t.get_size()) or None,
            align_bytes=max(0, t.get_align()) or None,
        )


class RecordLowerer:
    """Lower record declarations and fields through the shared context."""

    def __init__(self, context: LoweringContext) -> None:
        self.context = context

    def lower_top_level_record(self, cursor: cx.Cursor) -> list[Struct] | Struct | None:
        """Lower a top-level record declaration from the primary file."""
        if cursor.kind not in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
            return None
        if cursor.is_definition() and cursor.spelling:
            nested, struct = self.lower_record_definition(cursor)
            if nested:
                return nested + [struct]
            return struct
        if cursor.spelling and not self.context.registry.is_complete_record_decl(cursor):
            decl_id = self.context.registry.decl_id_for_cursor(cursor)
            return Struct(
                decl_id=decl_id,
                name=cursor.spelling,
                c_name=cursor.spelling,
                fields=[],
                size_bytes=0,
                align_bytes=0,
                is_union=(cursor.kind == cx.CursorKind.UNION_DECL),
                is_complete=False,
            )
        return None

    def lower_record_definition(self, cursor: cx.Cursor) -> tuple[list[Struct], Struct]:
        """Lower a complete struct/union definition and nested anonymous records."""
        decl_id, c_name, name, is_anonymous = self.context.registry.record_identity(cursor)
        cached = self.context.record_cache_by_decl_id.get(decl_id)
        if cached is not None:
            return [], cached

        struct = Struct(
            decl_id=decl_id,
            name=name,
            c_name=c_name,
            fields=[],
            size_bytes=max(0, cursor.type.get_size()),
            align_bytes=max(1, cursor.type.get_align()),
            is_union=(cursor.kind == cx.CursorKind.UNION_DECL),
            is_anonymous=is_anonymous,
        )
        self.context.record_cache_by_decl_id[decl_id] = struct

        nested: list[Struct] = []
        fields: list = []
        for child in cursor.get_children():
            if child.kind != cx.CursorKind.FIELD_DECL:
                continue
            field, nested_defs = self._lower_field(cursor.type, child)
            nested.extend(nested_defs)
            if field is not None:
                fields.append(field)
        struct.fields = fields
        self._apply_attributes(struct, cursor)
        return nested, struct

    def _lower_field(self, parent_type: cx.Type, cursor: cx.Cursor):
        field_name = cursor.spelling
        bit_offset = parent_type.get_offset(field_name) if field_name else -1
        byte_offset = bit_offset // 8 if bit_offset >= 0 else 0

        if cursor.is_bitfield():
            backing = self.context.type_lowerer.lower(cursor.type, TypeContext.FIELD)
            if not isinstance(backing, Primitive):
                return None, []
            return (
                Field(
                    name=field_name,
                    source_name=field_name,
                    type=backing,
                    byte_offset=byte_offset,
                    is_anonymous=not bool(field_name),
                    is_bitfield=True,
                    bit_offset=max(bit_offset, 0),
                    bit_width=cursor.get_bitfield_width(),
                ),
                [],
            )

        lowered_type, nested = self._lower_field_type(cursor)
        field = Field(
            name=field_name,
            source_name=field_name,
            type=lowered_type,
            byte_offset=byte_offset,
            is_anonymous=not bool(field_name),
        )
        return field, nested

    def _lower_field_type(self, cursor: cx.Cursor) -> tuple[Type, list[Struct]]:
        ft = cursor.type.get_canonical()
        if ft.kind != cx.TypeKind.RECORD:
            return self.context.type_lowerer.lower(cursor.type, TypeContext.FIELD), []

        decl = ft.get_declaration()
        definition = decl.get_definition()
        is_anon_record = (
            definition is not None
            and not decl.spelling
            and definition.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL)
        )
        if not is_anon_record:
            return self.context.type_lowerer.lower(cursor.type, TypeContext.FIELD), []

        nested_defs, inner = self.lower_record_definition(definition)
        return (
            StructRef(
                decl_id=inner.decl_id,
                name=inner.name,
                c_name=inner.c_name,
                is_union=inner.is_union,
                size_bytes=inner.size_bytes,
                is_anonymous=inner.is_anonymous,
            ),
            nested_defs + [inner],
        )

    @staticmethod
    def _apply_attributes(struct: Struct, cursor: cx.Cursor) -> None:
        packed = False
        requested_align: int | None = None
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.PACKED_ATTR:
                packed = True
            elif child.kind == cx.CursorKind.ALIGNED_ATTR:
                requested_align = struct.align_bytes
        struct.is_packed = packed
        struct.requested_align_bytes = requested_align


class DeclLowerer:
    """Lower top-level declarations into IR declarations."""

    def __init__(self, context: LoweringContext) -> None:
        self.context = context

    def lower_top_level_decl(self, cursor: cx.Cursor) -> list[Decl] | Decl | None:
        """Lower one primary-file top-level cursor."""
        k = cursor.kind
        if k == cx.CursorKind.FUNCTION_DECL:
            return self._build_function(cursor)
        if k in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
            return self.context.record_lowerer.lower_top_level_record(cursor)
        if k == cx.CursorKind.ENUM_DECL:
            if not cursor.is_definition():
                return None
            if not cursor.spelling:
                return self._anonymous_enum_as_consts(cursor)
            return self._build_enum(cursor)
        if k == cx.CursorKind.TYPEDEF_DECL:
            return self._build_typedef(cursor)
        if k == cx.CursorKind.VAR_DECL:
            return self._build_global_var(cursor)
        return None

    def collect_macros(self) -> list[Const]:
        """Lower supported primary-file macro definitions into `Const` nodes."""
        out: list[Const] = []
        for cursor in self.context.tu.cursor.walk_preorder():
            if cursor.kind != cx.CursorKind.MACRO_DEFINITION:
                continue
            if not self.context.frontend.is_primary_file_cursor(cursor):
                continue
            parsed = self.context.const_expr_parser.parse_macro(cursor)
            if parsed is None or parsed.primitive is None:
                continue
            out.append(Const(name=cursor.spelling, type=parsed.primitive, expr=parsed.expr))
        return out

    def _build_function(self, cursor: cx.Cursor) -> Function:
        fn_type = cursor.type
        ret_ir = self.context.type_lowerer.lower(fn_type.get_result(), TypeContext.RETURN)
        params: list[Param] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.PARM_DECL:
                param_type = self.context.type_lowerer.lower(child.type, TypeContext.PARAM)
                params.append(Param(name=child.spelling, type=param_type))

        is_variadic = (
            fn_type.kind == cx.TypeKind.FUNCTIONPROTO and fn_type.is_function_variadic()
        )
        if fn_type.kind == cx.TypeKind.FUNCTIONNOPROTO:
            self.context.append_diag(
                "warning",
                cursor,
                "function has no prototype (K&R-style); parameters may be incomplete",
            )
        return Function(
            decl_id=self.context.registry.decl_id_for_cursor(cursor),
            name=cursor.spelling,
            link_name=cursor.spelling,
            ret=ret_ir,
            params=params,
            is_variadic=is_variadic,
            calling_convention=self.context.compat.get_calling_convention(fn_type),
        )

    def _anonymous_enum_as_consts(self, cursor: cx.Cursor) -> list[Const]:
        underlying = self.context.primitive_resolver.resolve_primitive(cursor.enum_type)
        if underlying is None:
            underlying = Primitive("int", kind=PrimitiveKind.INT, is_signed=True, size_bytes=4)
        out: list[Const] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.ENUM_CONSTANT_DECL:
                out.append(Const(name=child.spelling, type=underlying, expr=IntLiteral(child.enum_value)))
        return out

    def _build_enum(self, cursor: cx.Cursor) -> Enum | None:
        c_name = cursor.spelling
        if not c_name:
            return None
        underlying = self.context.primitive_resolver.resolve_primitive(cursor.enum_type)
        if underlying is None:
            underlying = Primitive("int", kind=PrimitiveKind.INT, is_signed=True, size_bytes=4)
        enumerants: list[Enumerant] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.ENUM_CONSTANT_DECL:
                enumerants.append(
                    Enumerant(name=child.spelling, c_name=child.spelling, value=child.enum_value)
                )
        return Enum(
            decl_id=self.context.registry.decl_id_for_cursor(cursor),
            name=c_name,
            c_name=c_name,
            underlying=underlying,
            enumerants=enumerants,
        )

    def _build_typedef(self, cursor: cx.Cursor) -> Typedef:
        name = cursor.spelling
        ut = cursor.underlying_typedef_type
        aliased = self.context.type_lowerer.lower(ut, TypeContext.TYPEDEF)
        canonical = self.context.type_lowerer.lower(ut.get_canonical(), TypeContext.TYPEDEF)
        return Typedef(
            decl_id=self.context.registry.decl_id_for_cursor(cursor),
            name=name,
            aliased=aliased,
            canonical=canonical,
        )

    def _build_global_var(self, cursor: cx.Cursor) -> GlobalVar:
        parsed = self.context.const_expr_parser.parse_initializer(cursor)
        return GlobalVar(
            decl_id=self.context.registry.decl_id_for_cursor(cursor),
            name=cursor.spelling,
            link_name=cursor.spelling,
            type=self.context.type_lowerer.lower(cursor.type, TypeContext.PARAM),
            is_const=cursor.type.is_const_qualified(),
            initializer=None if parsed is None else parsed.expr,
        )

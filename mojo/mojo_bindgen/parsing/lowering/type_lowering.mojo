"""Clang types to recursive CIR; result construction is local to each call."""
from clang.cindex import Type, TypeKind, Cursor, CursorKind
from std.memory import ArcPointer
from ...ir import (
    CType,
    VoidType,
    IntType,
    IntKind,
    FloatType,
    QualifiedType,
    Qualifiers,
    CPointer,
    CArray,
    ArrayKind,
    CFunctionPtr,
    CParam,
    StructRef,
    EnumRef,
    TypeRef,
    AtomicType,
    VectorType,
    ComplexType,
    UnsupportedType,
    UnsupportedTypeCategory,
    IRDiagnostic,
)
from ..registry import RecordRegistry, decl_id, anonymous, make_struct_ref, RecordState
from ..frontend import children
from ...analysis.common import quoted
from .primitive import primitive, safe_align, safe_size, default_int
from .record_lowering import lower_record


__enum TypeContext(Equatable, ImplicitlyCopyable):
    case FIELD
    case PARAM
    case RETURN
    case TYPEDEF


def normalize(var t: Type) raises -> Type:
    if t.kind() == TypeKind.ELABORATED:
        return normalize(t.named_type())
    return t^


def qualifiers(ref t: Type) raises -> Qualifiers:
    return Qualifiers(t.is_const_qualified(), t.is_volatile_qualified(), t.is_restrict_qualified())


def calling_convention(ref t: Type) raises -> Optional[String]:
    var convention = t.calling_conv().name()
    if convention == "C" or convention == "DEFAULT":
        return None
    return convention^


def lower_type(
    mut registry: RecordRegistry, ref source: Type, ctx: TypeContext, cursor: Optional[Cursor] = {}
) raises -> CType:
    var t = normalize(source.copy())
    var kind = t.kind()
    if kind == TypeKind.VOID:
        return CType.void_type(VoidType())
    if kind == TypeKind.TYPEDEF:
        var decl = t.declaration()
        if not decl:
            raise Error("typedef has no declaration")
        var name = decl.value().spelling()
        if not name:
            name = t.spelling()
        var canonical = t.canonical()
        return CType.type_ref(
            TypeRef(decl_id(decl.value()), name^, ArcPointer(lower_type(registry, canonical, ctx)))
        )
    if kind == TypeKind.POINTER:
        var raw = t.pointee()
        var q = qualifiers(raw)
        var pointee = normalize(raw.copy())
        var canon = normalize(pointee.canonical())
        if canon.kind() == TypeKind.FUNCTION_PROTO or canon.kind() == TypeKind.FUNCTION_NO_PROTO:
            if (
                pointee.kind() != TypeKind.FUNCTION_PROTO
                and pointee.kind() != TypeKind.FUNCTION_NO_PROTO
            ):
                pointee = canon.copy()
            return CType.c_function_ptr(
                lower_fnptr(registry, pointee, ctx, cursor, max(0, t.size()), safe_align(t))
            )
        var lowered = lower_type(registry, pointee, ctx)
        if q.is_const or q.is_volatile or q.is_restrict:
            lowered = CType.qualified_type(QualifiedType(ArcPointer(lowered^), q.copy()))
        elif pointee.kind() == TypeKind.VOID:
            return CType.c_pointer(CPointer({}, max(0, t.size()), safe_align(t)))
        return CType.c_pointer(CPointer(ArcPointer(lowered^), max(0, t.size()), safe_align(t)))
    if kind == TypeKind.FUNCTION_PROTO or kind == TypeKind.FUNCTION_NO_PROTO:
        return CType.c_function_ptr(lower_fnptr(registry, t, ctx, cursor))
    if (
        kind == TypeKind.CONSTANT_ARRAY
        or kind == TypeKind.INCOMPLETE_ARRAY
        or kind == TypeKind.VARIABLE_ARRAY
        or kind == TypeKind.DEPENDENT_SIZED_ARRAY
    ):
        var element = t.array_element_type()
        var shape = ArrayKind.incomplete
        var count = Optional[Int]()
        if kind == TypeKind.CONSTANT_ARRAY:
            shape = ArrayKind.fixed
            count = t.array_size()
        elif kind == TypeKind.INCOMPLETE_ARRAY:
            if ctx == TypeContext.FIELD:
                shape = ArrayKind.flexible
        else:
            shape = ArrayKind.variable
        return CType.c_array(
            CArray(
                ArcPointer(lower_type(registry, element, ctx)),
                count^,
                shape,
                max(0, t.size()),
                safe_align(t),
            )
        )
    if kind == TypeKind.RECORD:
        var decl = t.declaration()
        if not decl:
            raise Error("record has no declaration")
        var key = decl_id(decl.value())
        if key in registry.states:
            return CType.struct_ref(make_struct_ref(registry.states[key].header()))
        var name = decl.value().spelling()
        if name:
            return CType.struct_ref(
                StructRef(
                    key^,
                    name.copy(),
                    name.copy(),
                    decl.value().kind() == CursorKind.UNION_DECL,
                    max(0, t.size()),
                    safe_align(t),
                    False,
                )
            )
        if key in registry.definitions:
            var definition = registry.definitions[key].copy()
            return CType.struct_ref(make_struct_ref(lower_record(registry, definition)))
        return CType.unsupported_type(
            UnsupportedType(
                UnsupportedTypeCategory.unsupported_extension,
                "__anonymous_record",
                "anonymous incomplete record reference cannot be named",
            )
        )
    if kind == TypeKind.ENUM:
        var decl = t.declaration()
        if not decl:
            return CType.int_type(default_int())
        var et = decl.value().enum_type()
        var p = primitive(et)
        if p:
            match p.value():
                case .int_type(v):
                    var name = decl.value().spelling()
                    if name:
                        return CType.enum_ref(
                            EnumRef(decl_id(decl.value()), name.copy(), name.copy(), v.copy())
                        )
                    return CType.int_type(v.copy())
                case _:
                    pass
        return CType.int_type(default_int())
    if kind == TypeKind.ATOMIC:
        var value = t.value_type()
        var inner: CType
        if value:
            inner = lower_type(registry, value.value(), ctx)
        else:
            inner = CType.unsupported_type(
                UnsupportedType(
                    UnsupportedTypeCategory.unsupported_extension,
                    t.spelling(),
                    "libclang did not expose atomic value type information",
                    safe_size(t),
                    safe_align(t),
                )
            )
        registry.diagnostics.append(__atomic_diag(t.spelling()))
        return CType.atomic_type(AtomicType(ArcPointer(inner^), safe_size(t), safe_align(t)))
    if kind == TypeKind.VECTOR or kind == TypeKind.EXT_VECTOR:
        var element = t.element_type()
        var count = t.element_count()
        return CType.vector_type(
            VectorType(
                ArcPointer(lower_type(registry, element, TypeContext.FIELD)),
                Optional[Int](count) if count >= 0 else Optional[Int](),
                max(0, t.size()),
                kind == TypeKind.EXT_VECTOR,
                safe_align(t),
            )
        )
    if kind == TypeKind.COMPLEX:
        var element = t.element_type()
        var p = primitive(element)
        if p:
            match p.value():
                case .float_type(v):
                    return CType.complex_type(
                        ComplexType(v.copy(), max(0, t.size()), safe_align(t))
                    )
                case _:
                    pass
        return CType.unsupported_type(
            UnsupportedType(
                UnsupportedTypeCategory.complex,
                t.spelling(),
                "complex element type is not a primitive scalar",
                safe_size(t),
                safe_align(t),
            )
        )
    var p = primitive(t)
    if p:
        return p.value().copy()
    var category = UnsupportedTypeCategory.unknown
    var reason = String("type is neither scalar nor otherwise modeled")
    if kind == TypeKind.INVALID:
        category = UnsupportedTypeCategory.invalid
        reason = "clang reported INVALID type kind"
    elif kind == TypeKind.UNEXPOSED:
        category = UnsupportedTypeCategory.unexposed
        reason = "clang reported UNEXPOSED type kind"
    var spelling = t.spelling()
    if kind == TypeKind.INVALID or kind == TypeKind.UNEXPOSED:
        registry.diagnostics.append(
            IRDiagnostic(
                "warning",
                String("invalid type kind" if kind == TypeKind.INVALID else "unexposed type kind")
                + ": "
                + quoted(spelling),
                "<type>",
                0,
                0,
            )
        )
    if not spelling:
        spelling = String(
            "invalid" if kind
            == TypeKind.INVALID else "unexposed" if kind
            == TypeKind.UNEXPOSED else "unknown"
        )
    return CType.unsupported_type(
        UnsupportedType(category, spelling^, reason^, safe_size(t), safe_align(t))
    )


def __atomic_diag(spelling: String) -> IRDiagnostic:
    from ...ir import IRDiagnostic

    return IRDiagnostic(
        "warning",
        "_Atomic uses Atomic[T] for layout-compatible scalars; unsupported atomic storage remains opaque: "
        + quoted(spelling),
        "<type>",
        0,
        0,
    )


def lower_fnptr(
    mut registry: RecordRegistry,
    ref t: Type,
    ctx: TypeContext,
    cursor: Optional[Cursor] = {},
    size: Int = 0,
    align: Optional[Int] = {},
) raises -> CFunctionPtr:
    var result = t.result()
    var ret = ArcPointer(lower_type(registry, result, ctx))
    var params = List[CParam]()
    var names = Optional[List[String]]()
    var variadic = False
    if t.kind() == TypeKind.FUNCTION_PROTO:
        var sugared = t.argument_types()
        var canonical = t.canonical()
        var adjusted = canonical.argument_types()
        for i in range(len(sugared)):
            var shape = normalize(sugared[i].copy())
            var actual = normalize(adjusted[i].copy())
            if shape.kind() == TypeKind.CONSTANT_ARRAY and actual.kind() == TypeKind.POINTER:
                shape = actual.copy()
            params.append(CParam("", ArcPointer(lower_type(registry, shape, ctx))))
        variadic = t.is_function_variadic()
    if cursor and len(params):
        var parameter_nodes = List[Cursor]()
        for child in children(cursor.value()):
            if child.kind() == CursorKind.PARM_DECL:
                parameter_nodes.append(child.copy())
        var eligible = len(parameter_nodes)
        if cursor.value().kind() == CursorKind.FUNCTION_DECL:
            eligible -= cursor.value().num_arguments()
        if eligible >= len(params):
            var values = List[String]()
            var any_name = False
            for i in range(len(params)):
                var name = parameter_nodes[i].spelling()
                any_name = any_name or Bool(name)
                values.append(name^)
            if any_name:
                names = values^
    return CFunctionPtr(
        ret^, params^, names^, variadic, calling_convention(t), False, size, align.copy()
    )

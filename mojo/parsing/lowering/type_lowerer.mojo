from mojo.ir import (
    Array,
    ArrayKind,
    AtomicType,
    ComplexType,
    EnumRef,
    FloatType,
    FunctionPtr,
    IntType,
    Param,
    Pointer,
    QualifiedType,
    Qualifiers,
    StructRef,
    TypeRef,
    UnsupportedType,
    Value,
    VectorType,
    VoidType,
)
from mojo.parsing.diagnostics import ParserDiagnosticSink
from mojo.parsing.lowering.primitive import (
    PrimitiveResolver,
    default_signed_int_primitive,
)
from mojo.parsing.registry import RecordRegistry
import clang.cindex as cx


@fieldwise_init
struct TypeContext(Equatable, Hashable, ImplicitlyCopyable):
    var value: Int
    comptime FIELD = 0
    comptime PARAM = 1
    comptime RETURN = 2
    comptime TYPEDEF = 3


def _normalize(t: cx.Type) raises -> cx.Type:
    if t.kind() == cx.TypeKind.ELABORATED:
        return _normalize(t.named_type())
    return t.copy()


def _qualifiers(t: cx.Type) raises -> Qualifiers:
    var qualifiers = Qualifiers()
    qualifiers.is_const = t.is_const_qualified()
    qualifiers.is_volatile = t.is_volatile_qualified()
    qualifiers.is_restrict = t.is_restrict_qualified()
    return qualifiers^


def _safe_size(t: cx.Type) raises -> Optional[Int]:
    return max(0, t.size()) or Optional[Int](None)


def _safe_align(t: cx.Type) raises -> Optional[Int]:
    return max(0, t.align()) or Optional[Int](None)


def _array_kind(t: cx.Type, ctx: TypeContext) raises -> ArrayKind:
    if t.kind() == cx.TypeKind.CONSTANT_ARRAY:
        return ArrayKind(ArrayKind.FIXED)
    if t.kind() == cx.TypeKind.INCOMPLETE_ARRAY:
        var x = ctx.value == Int(TypeContext.FIELD)

        return ArrayKind(ArrayKind.FLEXIBLE) if x else ArrayKind(
            ArrayKind.INCOMPLETE
        )
    if t.kind() in (
        cx.TypeKind.VARIABLE_ARRAY,
        cx.TypeKind.DEPENDENT_SIZED_ARRAY,
    ):
        return ArrayKind(ArrayKind.VARIABLE)
    return ArrayKind(ArrayKind.INCOMPLETE)


def _lower_void_pointer(
    qualifiers: Qualifiers,
    *,
    size_bytes: Optional[Int],
    align_bytes: Optional[Int],
) -> Type:
    if qualifiers == Qualifiers():
        var ptr = Pointer()
        ptr.pointee = None
        ptr.size_bytes = size_bytes or 0
        ptr.align_bytes = align_bytes
        return ptr^
    var q = QualifiedType()
    q.unqualified = VoidType()
    q.qualifiers = qualifiers.copy()
    var ptr = Pointer()
    ptr.pointee = Optional[Value](q^)
    ptr.size_bytes = size_bytes or 0
    ptr.align_bytes = align_bytes
    return ptr^

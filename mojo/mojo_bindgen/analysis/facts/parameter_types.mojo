"""C parameter adjustment, distinct from mapping an array stored in memory."""
from std.memory import ArcPointer
from ...ir import *
from .type_layout import peel_layout_wrappers


def decay_array_parameter(t: CType, pointer_size: Int, pointer_align: Optional[Int]) -> CType:
    var core = peel_layout_wrappers(t)
    if case .c_array(v) = core:
        var element = v.element.copy()
        if pointee_is_const(t) and not pointee_is_const(element[]):
            element = ArcPointer(
                CType.qualified_type(QualifiedType(element^, Qualifiers(is_const=True)))
            )
        return CType.c_pointer(CPointer(element^, pointer_size, pointer_align))
    return t.copy()


def pointee_is_const(t: CType) -> Bool:
    match t:
        case .qualified_type(v):
            return v.qualifiers.is_const or pointee_is_const(v.unqualified[])
        case .c_array(v):
            return pointee_is_const(v.element[])
        case .type_ref(v):
            return pointee_is_const(v.canonical[])
        case _:
            return False


def parameter_type(t: CType, abi: TargetABI) -> CType:
    return decay_array_parameter(t, abi.pointer_size_bytes, abi.pointer_align_bytes)

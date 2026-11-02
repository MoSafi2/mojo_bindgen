"""C parameter adjustment, independent of target-language array storage."""

from mojo_bindgen.ir import CArray, CPointer, CType, QualifiedType, Qualifiers, TargetABI, TypeRef

from .type_layout import peel_layout_wrappers


def decay_array_parameter(t: CType, pointer_size: int, pointer_align: int | None) -> CType:
    core = peel_layout_wrappers(t)
    if isinstance(core, CArray):
        element = core.element
        if pointee_is_const(t) and not pointee_is_const(element):
            element = QualifiedType(element, Qualifiers(is_const=True))
        return CPointer(element, pointer_size, pointer_align)
    return t


def pointee_is_const(t: CType) -> bool:
    if isinstance(t, QualifiedType):
        return t.qualifiers.is_const or pointee_is_const(t.unqualified)
    if isinstance(t, CArray):
        return pointee_is_const(t.element)
    if isinstance(t, TypeRef):
        return pointee_is_const(t.canonical)
    return False


def parameter_type(t: CType, abi: TargetABI) -> CType:
    return decay_array_parameter(t, abi.pointer_size_bytes, abi.pointer_align_bytes)

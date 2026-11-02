from std.memory import ArcPointer
from ...ir import *


def peel_layout_wrappers(t: CType) -> CType:
    match t:
        case .type_ref(v):
            return peel_layout_wrappers(v.canonical.ptr()[])
        case .qualified_type(v):
            return peel_layout_wrappers(v.unqualified.ptr()[])
        case _:
            return t.copy()


def _explicit(size: Optional[Int], align: Optional[Int]) -> Optional[Tuple[Int, Int]]:
    if size and align:
        return (size.value(), align.value())
    return {}


def type_layout(t: CType) -> Optional[Tuple[Int, Int]]:
    match t:
        case .type_ref(v):
            return type_layout(v.canonical.ptr()[])
        case .qualified_type(v):
            return type_layout(v.unqualified.ptr()[])
        case .atomic_type(v):
            var layout = _explicit(v.size_bytes, v.align_bytes)
            return layout if layout else type_layout(v.value_type.ptr()[])
        case .int_type(v):
            return _explicit(v.size_bytes, v.align_bytes)
        case .float_type(v):
            return _explicit(v.size_bytes, v.align_bytes)
        case .vector_type(v):
            return _explicit(v.size_bytes, v.align_bytes)
        case .struct_ref(v):
            return _explicit(v.size_bytes, v.align_bytes)
        case .c_pointer(v):
            return _explicit(v.size_bytes, v.align_bytes)
        case .c_function_ptr(v):
            return _explicit(v.size_bytes, v.align_bytes)
        case .opaque_record_ref(v):
            return _explicit(v.size_bytes, v.align_bytes)
        case .unsupported_type(v):
            return _explicit(v.size_bytes, v.align_bytes)
        case .c_array(v):
            return _explicit(v.size_bytes, v.align_bytes)
        case .enum_ref(v):
            return type_layout(CType.int_type(v.underlying.copy()))
        case .complex_type(v):
            if v.align_bytes:
                return (v.size_bytes, v.align_bytes.value())
            var element = type_layout(CType.float_type(v.element.copy()))
            if element:
                return (v.size_bytes, element.value()[1])
            return {}
        case .void_type(_):
            return {}


def type_align(t: CType) -> Optional[Int]:
    var layout = type_layout(t)
    if layout:
        return layout.value()[1]
    return {}


def type_size(t: CType) -> Optional[Int]:
    var core = peel_layout_wrappers(t)
    match core:
        case .enum_ref(v):
            return v.underlying.size_bytes
        case .int_type(v):
            return v.size_bytes
        case .float_type(v):
            return v.size_bytes
        case .c_array(v):
            return (
                v.size_bytes if v.size_bytes > 0
                or (v.size and v.size.value() == 0) else Optional[Int]()
            )
        case .complex_type(v):
            return v.size_bytes
        case .vector_type(v):
            return v.size_bytes
        case .c_pointer(v):
            return v.size_bytes
        case .c_function_ptr(v):
            return v.size_bytes
        case .struct_ref(v):
            return v.size_bytes
        case .opaque_record_ref(v):
            return v.size_bytes
        case .unsupported_type(v):
            return v.size_bytes
        case .atomic_type(v):
            return v.size_bytes if v.size_bytes else type_size(v.value_type[])
        case .void_type(_) | .type_ref(_) | .qualified_type(_):
            return {}

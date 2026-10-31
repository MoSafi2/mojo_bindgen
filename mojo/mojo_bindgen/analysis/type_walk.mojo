from std.memory import ArcPointer
from ..ir import *


def _children(t: CType) -> List[ArcPointer[CType]]:
    var result = List[ArcPointer[CType]]()
    match t:
        case .qualified_type(v):
            result.append(v.unqualified.copy())
        case .atomic_type(v):
            result.append(v.value_type.copy())
        case .type_ref(v):
            result.append(v.canonical.copy())
        case .c_pointer(v):
            if v.pointee:
                result.append(v.pointee.value().copy())
        case .c_array(v):
            result.append(v.element.copy())
        case .vector_type(v):
            result.append(v.element.copy())
        case .complex_type(v):
            result.append(ArcPointer(CType.float_type(v.element.copy())))
        case .enum_ref(v):
            result.append(ArcPointer(CType.int_type(v.underlying.copy())))
        case .c_function_ptr(v):
            result.append(v.ret.copy())
            for p in v.params:
                result.append(p.type.copy())
        case .void_type(_) | .int_type(_) | .float_type(_) | .struct_ref(_) | .opaque_record_ref(
            _
        ) | .unsupported_type(_):
            pass
    return result^


def _validate(node: ArcPointer[CType], mut active: List[ArcPointer[CType]]) raises:
    for parent in active:
        if node.ptr() == parent.ptr():
            raise Error("structural CIR type cycle")
    active.append(node.copy())
    for child in _children(node.ptr()[]):
        _validate(child, active)
    _ = active.pop()


def validate_type_tree(root: CType) raises:
    """Follow owning children only; shared DAG nodes and nominal recursion are valid."""
    var active = List[ArcPointer[CType]]()
    for child in _children(root):
        _validate(child, active)


struct TypeWalkOptions(Copyable, Movable):
    var peel_typeref: Bool
    var peel_qualified: Bool
    var peel_atomic: Bool
    var descend_pointer: Bool
    var descend_array: Bool
    var descend_function_ptr: Bool
    var descend_vector_element: Bool

    def __init__(
        out self,
        peel_typeref: Bool = True,
        peel_qualified: Bool = True,
        peel_atomic: Bool = True,
        descend_pointer: Bool = True,
        descend_array: Bool = True,
        descend_function_ptr: Bool = True,
        descend_vector_element: Bool = False,
    ):
        self.peel_typeref = peel_typeref
        self.peel_qualified = peel_qualified
        self.peel_atomic = peel_atomic
        self.descend_pointer = descend_pointer
        self.descend_array = descend_array
        self.descend_function_ptr = descend_function_ptr
        self.descend_vector_element = descend_vector_element


def _walk(node: ArcPointer[CType], options: TypeWalkOptions, mut out: List[ArcPointer[CType]]):
    out.append(node.copy())
    var children = List[ArcPointer[CType]]()
    match node.ptr()[]:
        case .type_ref(v):
            if options.peel_typeref:
                children.append(v.canonical.copy())
        case .qualified_type(v):
            if options.peel_qualified:
                children.append(v.unqualified.copy())
        case .atomic_type(v):
            if options.peel_atomic:
                children.append(v.value_type.copy())
        case .c_pointer(v):
            if options.descend_pointer and v.pointee:
                children.append(v.pointee.value().copy())
        case .c_array(v):
            if options.descend_array:
                children.append(v.element.copy())
        case .c_function_ptr(v):
            if options.descend_function_ptr:
                children.append(v.ret.copy())
                for p in v.params:
                    children.append(p.type.copy())
        case .vector_type(v):
            if options.descend_vector_element:
                children.append(v.element.copy())
        case .void_type(_) | .int_type(_) | .float_type(_) | .struct_ref(_) | .enum_ref(
            _
        ) | .opaque_record_ref(_) | .unsupported_type(_) | .complex_type(_):
            pass
    for child in children:
        _walk(child, options, out)


def iter_type_nodes(
    t: CType, options: TypeWalkOptions = TypeWalkOptions()
) -> List[ArcPointer[CType]]:
    var result = List[ArcPointer[CType]]()
    _walk(ArcPointer(t.copy()), options, result)
    return result^


def _target_children(t: MojoType) -> List[ArcPointer[MojoType]]:
    var out = List[ArcPointer[MojoType]]()
    match t:
        case .mojo_pointer(v):
            if v.pointee:
                out.append(v.pointee.value().copy())
        case .mojo_array(v):
            out.append(v.element.copy())
        case .mojo_function_ptr(v):
            out.append(v.ret.copy())
            for p in v.params:
                out.append(p.type.copy())
        case .parametric_type(v):
            for arg in v.args:
                match arg:
                    case .type_arg(a):
                        out.append(a.type.copy())
                    case _:
                        pass
        case .builtin_type(_) | .named_type(_):
            pass
    return out^


def _validate_target(node: ArcPointer[MojoType], mut active: List[ArcPointer[MojoType]]) raises:
    for prior in active:
        if node.ptr() == prior.ptr():
            raise Error("structural MojoIR type cycle")
    active.append(node.copy())
    for child in _target_children(node.ptr()[]):
        _validate_target(child, active)
    _ = active.pop()


def validate_type_tree(root: MojoType) raises:
    var active = List[ArcPointer[MojoType]]()
    for child in _target_children(root):
        _validate_target(child, active)

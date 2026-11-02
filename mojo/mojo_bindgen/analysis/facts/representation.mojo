"""Target storage geometry; source offsets are requirements, never target facts."""
from ...ir import *
from .target import TargetQueries


__enum RepresentationKind(Equatable, ImplicitlyCopyable, Movable):
    case VALUE
    case STORAGE
    case UNSUPPORTED


@fieldwise_init
struct TypeRepresentationFacts(Copyable, Movable):
    var kind: RepresentationKind
    var layout: Optional[Tuple[Int, Int]]
    var reason: String


def storage_type(size: Optional[Int], align: Optional[Int]) -> MojoType:
    if not size or not align:
        return MojoType.builtin_type(BuiltinType(MojoBuiltin.UNSUPPORTED))
    var n = size.value()
    var a = align.value()
    if n <= 0 or a <= 0 or (a & (a - 1)) != 0 or a > (1 << 29) or n % a:
        return MojoType.builtin_type(BuiltinType(MojoBuiltin.UNSUPPORTED))
    return MojoType.opaque_storage_type(OpaqueStorageType(n, a))


def target_layout(t: MojoType, queries: TargetQueries) raises -> Optional[Tuple[Int, Int]]:
    match t:
        case .builtin_type(v):
            return queries.builtin_layout(v.name)
        case .opaque_storage_type(v):
            if case .opaque_storage_type(_) = storage_type(v.size_bytes, v.align_bytes):
                return (v.size_bytes, v.align_bytes)
            return {}
        case .named_type(v):
            if v.name == "UInt" or v.name == "Int":
                return (queries.abi.pointer_size_bytes, queries.abi.pointer_align_bytes)
            for prefix in [String("UInt"), String("Int"), String("Float")]:
                if v.name.startswith(prefix):
                    var suffix = String(v.name[byte = prefix.byte_length() :])
                    for bits in [8, 16, 32, 64, 128]:
                        if suffix == String(bits):
                            var width = bits // 8
                            return (
                                width,
                                16 if width == 16 else min(width, queries.abi.pointer_align_bytes),
                            )
            return {}
        case .mojo_pointer(_) | .mojo_function_ptr(_):
            return (queries.abi.pointer_size_bytes, queries.abi.pointer_align_bytes)
        case .mojo_array(v):
            var element = target_layout(v.element[], queries)
            if not element or v.size < 0:
                return {}
            return (element.value()[0] * v.size, element.value()[1])
        case .parametric_type(v):
            if v.base == ParametricBase.ATOMIC:
                if len(v.args) == 1:
                    if case .type_arg(a) = v.args[0]:
                        return target_layout(a.type[], queries)
                return {}
            if v.base != ParametricBase.SIMD and v.base != ParametricBase.COMPLEX_SIMD:
                return {}
            var dtype = String()
            var count = 0
            for arg in v.args:
                match arg:
                    case .d_type_arg(a):
                        dtype = a.value.copy()
                    case .const_arg(a):
                        count = a.value.to_int()
                    case _:
                        pass
            if count <= 0 or (count & (count - 1)) != 0:
                return {}
            var width = 1 if dtype == "DType.bool" else 0
            for bits in [8, 16, 32, 64, 128]:
                for prefix in [String("int"), String("uint"), String("float")]:
                    if dtype == "DType." + prefix + String(bits):
                        width = bits // 8
            if width == 0:
                return {}
            var size = width * count
            return (size * (2 if v.base == ParametricBase.COMPLEX_SIMD else 1), size)


def contains_storage(t: MojoType) -> Bool:
    match t:
        case .opaque_storage_type(_):
            return True
        case .builtin_type(v):
            return v.name == MojoBuiltin.UNSUPPORTED
        case .mojo_array(v):
            return contains_storage(v.element[])
        case .parametric_type(v):
            for arg in v.args:
                if case .type_arg(a) = arg:
                    if contains_storage(a.type[]):
                        return True
            return False
        case .named_type(_) | .mojo_pointer(_) | .mojo_function_ptr(_):
            return False

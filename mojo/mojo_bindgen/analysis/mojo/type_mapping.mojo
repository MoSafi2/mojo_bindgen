"""Pure CIR-to-MojoIR type mapping with explicit, fixed target queries."""
from ..calling_convention import require_c_calling_convention


from std.memory import ArcPointer
from ...ir import *
from ..common import normalized_name
from ..facts.target import TargetQueries
from ..facts.parameter_types import parameter_type, pointee_is_const
from ..facts.representation import (
    storage_type,
    target_layout,
    contains_storage,
    TypeRepresentationFacts,
    RepresentationKind,
)
from ..facts.type_layout import type_layout, peel_layout_wrappers
from ..type_walk import validate_type_tree


def _pointer(
    var pointee: Optional[ArcPointer[MojoType]] = {},
    mutability: PointerMutability = PointerMutability.MUT,
    nullable: Bool = False,
) -> MojoType:
    return MojoType.mojo_pointer(
        MojoPointer(pointee^, mutability, PointerOrigin.EXTERNAL, nullable)
    )


def _int_dtype(v: IntType) -> Optional[String]:
    if v.int_kind == IntKind.BOOL:
        return String("DType.bool")
    var signed: Bool
    match v.int_kind:
        case .CHAR_S | .SCHAR | .SHORT | .INT | .LONG | .LONGLONG | .INT128:
            signed = True
        case .CHAR_U | .UCHAR | .USHORT | .UINT | .ULONG | .ULONGLONG | .UINT128:
            signed = False
        case .BOOL | .WCHAR | .CHAR16 | .CHAR32 | .EXT_INT:
            return {}
    if (
        v.size_bytes != 1
        and v.size_bytes != 2
        and v.size_bytes != 4
        and v.size_bytes != 8
        and v.size_bytes != 16
    ):
        return {}
    return String("DType." + ("int" if signed else "uint") + String(v.size_bytes * 8))


@fieldwise_init
struct _ScalarInfo(Copyable, Movable):
    var dtype: Optional[String]
    var size: Optional[Int]
    var alignment: Optional[Int]
    var scalar: Bool


def _scalar_info(t: CType, queries: TargetQueries) -> _ScalarInfo:
    match t:
        case .type_ref(v):
            return _scalar_info(v.canonical.ptr()[], queries)
        case .qualified_type(v):
            return _scalar_info(v.unqualified.ptr()[], queries)
        case .atomic_type(v):
            return _scalar_info(v.value_type.ptr()[], queries)
        case .int_type(v):
            return _ScalarInfo(_int_dtype(v), v.size_bytes, v.align_bytes, True)
        case .float_type(v):
            return _ScalarInfo(queries.float_dtype(v), v.size_bytes, v.align_bytes, True)
        case .void_type(_):
            return _ScalarInfo({}, {}, {}, True)
        case .c_pointer(_) | .c_array(_) | .c_function_ptr(_) | .struct_ref(_) | .enum_ref(
            _
        ) | .opaque_record_ref(_) | .unsupported_type(_) | .vector_type(_) | .complex_type(_):
            return _ScalarInfo({}, {}, {}, False)


def _storage_size(t: CType) -> Optional[Int]:
    match t:
        case .type_ref(v):
            return _storage_size(v.canonical.ptr()[])
        case .qualified_type(v):
            return _storage_size(v.unqualified.ptr()[])
        case .atomic_type(v):
            return v.size_bytes
        case .int_type(v):
            return v.size_bytes
        case .float_type(v):
            return v.size_bytes
        case .c_pointer(v):
            return v.size_bytes
        case .c_array(v):
            return v.size_bytes
        case .c_function_ptr(v):
            return v.size_bytes
        case .struct_ref(v):
            return v.size_bytes
        case .opaque_record_ref(v):
            return v.size_bytes
        case .unsupported_type(v):
            return v.size_bytes
        case .vector_type(v):
            return v.size_bytes
        case .complex_type(v):
            return v.size_bytes
        case .void_type(_) | .enum_ref(_):
            return {}


def _stripped_storage(t: CType) -> Optional[Int]:
    match t:
        case .type_ref(v):
            return _stripped_storage(v.canonical.ptr()[])
        case .qualified_type(v):
            return _stripped_storage(v.unqualified.ptr()[])
        case .atomic_type(v):
            return _stripped_storage(v.value_type.ptr()[])
        case _:
            return _storage_size(t)


@fieldwise_init
struct MapTypePass(Copyable, Movable):
    var queries: TargetQueries

    def run(self, t: CType) raises -> MojoType:
        validate_type_tree(t)
        return self._map(t)

    def representation(self, t: CType) raises -> TypeRepresentationFacts:
        var mapped = self.run(t)
        var kind = RepresentationKind.VALUE
        var reason = String()
        if contains_storage(mapped):
            kind = RepresentationKind.STORAGE
            reason = "type has storage without a supported value representation"
            if case .builtin_type(v) = mapped:
                if v.name == MojoBuiltin.UNSUPPORTED:
                    kind = RepresentationKind.UNSUPPORTED
                    reason = "type has no known representable storage geometry"
        return TypeRepresentationFacts(kind, target_layout(mapped, self.queries), reason^)

    def value_supported(self, t: CType) raises -> Bool:
        match t:
            case .type_ref(v):
                return self.value_supported(v.canonical[])
            case .qualified_type(v):
                return self.value_supported(v.unqualified[])
            case _:
                return not contains_storage(self.run(t))

    def _primitive(self, v: IntType) raises -> MojoType:
        var kind = v.int_kind
        if kind == IntKind.CHAR_S or kind == IntKind.CHAR_U:
            var unsigned = self.queries.default_char_is_unsigned()
            if unsigned:
                if (kind == IntKind.CHAR_U) == unsigned.value():
                    return MojoType.builtin_type(BuiltinType(MojoBuiltin.C_CHAR))
                return MojoType.named_type(NamedType("UInt8" if kind == IntKind.CHAR_U else "Int8"))
        if (
            kind == IntKind.INT128
            or kind == IntKind.UINT128
            or kind == IntKind.WCHAR
            or kind == IntKind.CHAR16
            or kind == IntKind.CHAR32
            or kind == IntKind.EXT_INT
        ):
            if (
                v.size_bytes == 1
                or v.size_bytes == 2
                or v.size_bytes == 4
                or v.size_bytes == 8
                or v.size_bytes == 16
            ):
                var name = String(
                    (
                        "UInt" if kind == IntKind.UINT128
                        or kind == IntKind.CHAR16
                        or kind == IntKind.CHAR32 else "Int"
                    )
                    + String(v.size_bytes * 8)
                )
                if name == "Int128":
                    return MojoType.builtin_type(BuiltinType(MojoBuiltin.INT128))
                if name == "UInt128":
                    return MojoType.builtin_type(BuiltinType(MojoBuiltin.UINT128))
                return MojoType.named_type(NamedType(name^))
        var builtin: MojoBuiltin
        match kind:
            case .BOOL:
                builtin = MojoBuiltin.BOOL
            case .CHAR_S:
                builtin = MojoBuiltin.C_CHAR
            case .CHAR_U | .UCHAR:
                builtin = MojoBuiltin.C_UCHAR
            case .SCHAR:
                builtin = MojoBuiltin.INT8
            case .SHORT:
                builtin = MojoBuiltin.C_SHORT
            case .USHORT:
                builtin = MojoBuiltin.C_USHORT
            case .INT:
                builtin = MojoBuiltin.C_INT
            case .UINT:
                builtin = MojoBuiltin.C_UINT
            case .LONG:
                builtin = MojoBuiltin.C_LONG
            case .ULONG:
                builtin = MojoBuiltin.C_ULONG
            case .LONGLONG:
                builtin = MojoBuiltin.C_LONG_LONG
            case .ULONGLONG:
                builtin = MojoBuiltin.C_ULONG_LONG
            case .INT128 | .UINT128 | .WCHAR | .CHAR16 | .CHAR32 | .EXT_INT:
                raise Error(
                    "no Mojo primitive builtin registered for IntType key <IntKind."
                    + kind.value()
                    + ": '"
                    + kind.value()
                    + "'>"
                )
        return MojoType.builtin_type(BuiltinType(builtin))

    def _float(self, v: FloatType) -> MojoType:
        if not self.queries.float_compatible(v):
            return storage_type(v.size_bytes, v.align_bytes)
        var format = self.queries.float_format(v.float_kind)
        if format == FloatFormat.BINARY16:
            return MojoType.builtin_type(BuiltinType(MojoBuiltin.FLOAT16))
        if format == FloatFormat.BINARY32:
            return MojoType.builtin_type(BuiltinType(MojoBuiltin.C_FLOAT))
        return MojoType.builtin_type(BuiltinType(MojoBuiltin.C_DOUBLE))

    def _pointee(self, t: CType, var mutability: PointerMutability) raises -> MojoType:
        if pointee_is_const(t):
            mutability = PointerMutability.IMMUT
        match t:
            case .void_type(_):
                return _pointer(mutability=mutability, nullable=True)
            case _:
                var mapped = self._map(t)
                if not self.value_supported(t):
                    if case .builtin_type(v) = self._map(peel_layout_wrappers(t)):
                        if v.name == MojoBuiltin.UNSUPPORTED:
                            return _pointer(mutability=mutability, nullable=True)
                return _pointer(ArcPointer(mapped^), mutability, True)

    def _callback_value(self, t: CType, result: Bool = False) raises -> Bool:
        match t:
            case .type_ref(v):
                return self._callback_value(v.canonical[], result)
            case .qualified_type(v):
                return self._callback_value(v.unqualified[], result)
            case .enum_ref(v):
                return self._callback_value(CType.int_type(v.underlying.copy()))
            case .void_type(_):
                return result
            case .int_type(v):
                return v.int_kind != IntKind.EXT_INT and not contains_storage(self._map(t))
            case .float_type(v):
                return v.float_kind != FloatKind.FLOAT16 and not contains_storage(self._map(t))
            case .c_pointer(_) | .c_function_ptr(_):
                return not contains_storage(self._map(t))
            case _:
                return False

    def _map(self, t: CType) raises -> MojoType:
        var mapped = self._map_unchecked(t)
        match t:
            case .int_type(_) | .float_type(_) | .atomic_type(_) | .vector_type(_) | .complex_type(
                _
            ) | .c_pointer(_) | .c_function_ptr(_):
                var source = type_layout(t)
                var target = target_layout(mapped, self.queries)
                if source and (not target or source.value() != target.value()):
                    return storage_type(source.value()[0], source.value()[1])
            case .c_array(v):
                if v.array_kind == ArrayKind.fixed and v.size_bytes > 0 and v.align_bytes:
                    var target = target_layout(mapped, self.queries)
                    if target and (
                        target.value()[0] != v.size_bytes
                        or target.value()[1] != v.align_bytes.value()
                    ):
                        return storage_type(v.size_bytes, v.align_bytes)
            case _:
                pass
        return mapped^

    def _map_unchecked(self, t: CType) raises -> MojoType:
        match t:
            case .void_type(_):
                return MojoType.builtin_type(BuiltinType(MojoBuiltin.NONE))
            case .int_type(v):
                try:
                    return self._primitive(v)
                except:
                    return storage_type(v.size_bytes, v.align_bytes)
            case .float_type(v):
                return self._float(v)
            case .qualified_type(v):
                return self._map(v.unqualified.ptr()[])
            case .type_ref(v):
                return MojoType.named_type(NamedType(normalized_name(v.name)))
            case .struct_ref(v):
                return MojoType.named_type(NamedType(normalized_name(v.name)))
            case .enum_ref(v):
                return MojoType.named_type(NamedType(normalized_name(v.name)))
            case .opaque_record_ref(v):
                return storage_type(v.size_bytes, v.align_bytes)
            case .c_pointer(v):
                if not v.pointee:
                    return _pointer(nullable=True)
                match v.pointee.value().ptr()[]:
                    case .qualified_type(q):
                        return self._pointee(
                            q.unqualified.ptr()[],
                            PointerMutability.IMMUT if q.qualifiers.is_const else PointerMutability.MUT,
                        )
                    case _:
                        return self._pointee(v.pointee.value().ptr()[], PointerMutability.MUT)
            case .c_array(v):
                if v.array_kind == ArrayKind.fixed and v.size:
                    return MojoType.mojo_array(
                        MojoArray(ArcPointer(self._map(v.element.ptr()[])), v.size.value())
                    )
                if v.array_kind == ArrayKind.flexible and not v.size:
                    return MojoType.mojo_array(
                        MojoArray(ArcPointer(self._map(v.element.ptr()[])), 0)
                    )
                return _pointer(ArcPointer(self._map(v.element.ptr()[])))
            case .c_function_ptr(v):
                require_c_calling_convention(v.calling_convention)
                var compatible = (
                    self.queries.supported_c_abi()
                    and not v.is_variadic
                    and self._callback_value(v.ret[], True)
                )
                for p in v.params:
                    compatible = compatible and self._callback_value(
                        parameter_type(p.type[], self.queries.abi)
                    )
                if not compatible:
                    return _pointer(nullable=True)
                var params = List[MojoParam]()
                for i in range(len(v.params)):
                    var name = String()
                    if v.param_names and i < len(v.param_names.value()):
                        name = v.param_names.value()[i].copy()
                    params.append(
                        MojoParam(
                            name^,
                            ArcPointer(
                                self._map(parameter_type(v.params[i].type[], self.queries.abi))
                            ),
                        )
                    )
                var abi = String("C")
                return MojoType.mojo_function_ptr(
                    MojoFunctionPtr(ArcPointer(self._map(v.ret.ptr()[])), params^, abi^)
                )
            case .atomic_type(v):
                var info = _scalar_info(v.value_type.ptr()[], self.queries)
                if (
                    info.dtype
                    and info.scalar
                    and (not v.size_bytes or v.size_bytes == info.size)
                    and (not v.align_bytes or v.align_bytes == info.alignment)
                ):
                    var args = List[ParametricArg]()
                    args.append(
                        ParametricArg.type_arg(TypeArg(ArcPointer(self._map(v.value_type.ptr()[]))))
                    )
                    return MojoType.parametric_type(ParametricType(ParametricBase.ATOMIC, args^))
                var size = v.size_bytes
                if not size or size.value() == 0:
                    size = _stripped_storage(v.value_type.ptr()[])
                if size and size.value() != 0:
                    return storage_type(size, v.align_bytes)
                raise Error("atomic storage has no representable scalar type or known size")
            case .vector_type(v):
                if not v.count:
                    return storage_type(v.size_bytes, v.align_bytes)
                var info = _scalar_info(v.element.ptr()[], self.queries)
                if info.dtype and not contains_storage(self._map(v.element[])):
                    var args = List[ParametricArg]()
                    args.append(ParametricArg.d_type_arg(DTypeArg(info.dtype.value().copy())))
                    args.append(ParametricArg.const_arg(ConstArg(v.count.value())))
                    return MojoType.parametric_type(ParametricType(ParametricBase.SIMD, args^))
                return storage_type(v.size_bytes, v.align_bytes)
            case .complex_type(v):
                var dtype = self.queries.float_dtype(v.element)
                if dtype and self.queries.float_compatible(v.element):
                    var args = List[ParametricArg]()
                    args.append(ParametricArg.d_type_arg(DTypeArg(dtype.value().copy())))
                    args.append(ParametricArg.const_arg(ConstArg(1)))
                    return MojoType.parametric_type(
                        ParametricType(ParametricBase.COMPLEX_SIMD, args^)
                    )
                return storage_type(v.size_bytes, v.align_bytes)
            case .unsupported_type(v):
                if v.size_bytes and v.size_bytes.value() > 0:
                    return storage_type(v.size_bytes, v.align_bytes)
                return MojoType.builtin_type(BuiltinType(MojoBuiltin.UNSUPPORTED))


def map_type(t: CType, queries: TargetQueries) raises -> MojoType:
    return MapTypePass(queries.copy()).run(t)


def exact_width_stdint_alias_type(name: String) -> Optional[NamedType]:
    match name:
        case "int8_t":
            return NamedType("Int8")
        case "uint8_t":
            return NamedType("UInt8")
        case "int16_t":
            return NamedType("Int16")
        case "uint16_t":
            return NamedType("UInt16")
        case "int32_t":
            return NamedType("Int32")
        case "uint32_t":
            return NamedType("UInt32")
        case "int64_t":
            return NamedType("Int64")
        case "uint64_t":
            return NamedType("UInt64")
        case "size_t":
            return NamedType("UInt")
        case "ssize_t":
            return NamedType("Int")
        case _:
            return {}

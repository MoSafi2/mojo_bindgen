"""Recursive production type payloads; published values are borrowed by passes."""

from std.memory import ArcPointer


__enum IntKind(Equatable, ImplicitlyCopyable, Movable):
    case BOOL
    case CHAR_S
    case CHAR_U
    case SCHAR
    case UCHAR
    case SHORT
    case USHORT
    case INT
    case UINT
    case LONG
    case ULONG
    case LONGLONG
    case ULONGLONG
    case INT128
    case UINT128
    case WCHAR
    case CHAR16
    case CHAR32
    case EXT_INT

    def value(self) -> String:
        match self:
            case .BOOL:
                return "BOOL"
            case .CHAR_S:
                return "CHAR_S"
            case .CHAR_U:
                return "CHAR_U"
            case .SCHAR:
                return "SCHAR"
            case .UCHAR:
                return "UCHAR"
            case .SHORT:
                return "SHORT"
            case .USHORT:
                return "USHORT"
            case .INT:
                return "INT"
            case .UINT:
                return "UINT"
            case .LONG:
                return "LONG"
            case .ULONG:
                return "ULONG"
            case .LONGLONG:
                return "LONGLONG"
            case .ULONGLONG:
                return "ULONGLONG"
            case .INT128:
                return "INT128"
            case .UINT128:
                return "UINT128"
            case .WCHAR:
                return "WCHAR"
            case .CHAR16:
                return "CHAR16"
            case .CHAR32:
                return "CHAR32"
            case .EXT_INT:
                return "EXT_INT"


__enum FloatKind(Equatable, ImplicitlyCopyable, Movable):
    case FLOAT16
    case FLOAT
    case DOUBLE
    case LONG_DOUBLE
    case FLOAT128

    def value(self) -> String:
        match self:
            case .FLOAT16:
                return "FLOAT16"
            case .FLOAT:
                return "FLOAT"
            case .DOUBLE:
                return "DOUBLE"
            case .LONG_DOUBLE:
                return "LONG_DOUBLE"
            case .FLOAT128:
                return "FLOAT128"


__enum PointerMutability(Equatable, ImplicitlyCopyable, Movable):
    case MUT
    case IMMUT

    def value(self) -> String:
        match self:
            case .MUT:
                return "mut"
            case .IMMUT:
                return "immut"


__enum PointerOrigin(Equatable, ImplicitlyCopyable, Movable):
    case EXTERNAL
    case ANY

    def value(self) -> String:
        match self:
            case .EXTERNAL:
                return "external"
            case .ANY:
                return "any"


__enum ByteOrder(Equatable, ImplicitlyCopyable, Movable):
    case LITTLE
    case BIG

    def value(self) -> String:
        match self:
            case .LITTLE:
                return "little"
            case .BIG:
                return "big"


__enum MojoBuiltin(Equatable, ImplicitlyCopyable, Movable):
    case NONE
    case BOOL
    case INT8
    case UINT8
    case INT128
    case UINT128
    case FLOAT16
    case C_CHAR
    case C_UCHAR
    case C_SHORT
    case C_USHORT
    case C_INT
    case C_UINT
    case C_LONG
    case C_ULONG
    case C_LONG_LONG
    case C_ULONG_LONG
    case C_FLOAT
    case C_DOUBLE
    case UNSUPPORTED

    def value(self) -> String:
        match self:
            case .NONE:
                return "NoneType"
            case .BOOL:
                return "Bool"
            case .INT8:
                return "Int8"
            case .UINT8:
                return "UInt8"
            case .INT128:
                return "Int128"
            case .UINT128:
                return "UInt128"
            case .FLOAT16:
                return "Float16"
            case .C_CHAR:
                return "c_char"
            case .C_UCHAR:
                return "c_uchar"
            case .C_SHORT:
                return "c_short"
            case .C_USHORT:
                return "c_ushort"
            case .C_INT:
                return "c_int"
            case .C_UINT:
                return "c_uint"
            case .C_LONG:
                return "c_long"
            case .C_ULONG:
                return "c_ulong"
            case .C_LONG_LONG:
                return "c_long_long"
            case .C_ULONG_LONG:
                return "c_ulong_long"
            case .C_FLOAT:
                return "c_float"
            case .C_DOUBLE:
                return "c_double"
            case .UNSUPPORTED:
                return "unsupported"


__enum ParametricBase(Equatable, ImplicitlyCopyable, Movable):
    case SIMD
    case COMPLEX_SIMD
    case ATOMIC
    case UNSAFE_UNION

    def value(self) -> String:
        match self:
            case .SIMD:
                return "SIMD"
            case .COMPLEX_SIMD:
                return "ComplexSIMD"
            case .ATOMIC:
                return "Atomic"
            case .UNSAFE_UNION:
                return "UnsafeUnion"


__enum ArrayKind(Equatable, ImplicitlyCopyable, Movable):
    case fixed
    case incomplete
    case flexible
    case variable

    def value(self) -> String:
        match self:
            case .fixed:
                return "fixed"
            case .incomplete:
                return "incomplete"
            case .flexible:
                return "flexible"
            case .variable:
                return "variable"


__enum UnsupportedTypeCategory(Equatable, ImplicitlyCopyable, Movable):
    case unexposed
    case vector
    case complex
    case block
    case objc
    case unsupported_extension
    case invalid
    case unknown

    def value(self) -> String:
        match self:
            case .unexposed:
                return "unexposed"
            case .vector:
                return "vector"
            case .complex:
                return "complex"
            case .block:
                return "block"
            case .objc:
                return "objc"
            case .unsupported_extension:
                return "unsupported_extension"
            case .invalid:
                return "invalid"
            case .unknown:
                return "unknown"


struct DocComment(Copyable, Movable):
    var text: String
    var brief: Optional[String]
    var source: String

    def __init__(
        out self,
        var text: String,
        var brief: Optional[String] = {},
        var source: String = "clang_raw",
    ):
        self.text = text^
        self.brief = brief^
        self.source = source^


struct Qualifiers(Copyable, Movable):
    var is_const: Bool
    var is_volatile: Bool
    var is_restrict: Bool

    def __init__(
        out self,
        var is_const: Bool = False,
        var is_volatile: Bool = False,
        var is_restrict: Bool = False,
    ):
        self.is_const = is_const
        self.is_volatile = is_volatile
        self.is_restrict = is_restrict


struct VoidType(Copyable, Movable):
    def __init__(out self):
        pass


struct IntType(Copyable, Movable):
    var int_kind: IntKind
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var ext_bits: Optional[Int]

    def __init__(
        out self,
        var int_kind: IntKind,
        var size_bytes: Int,
        var align_bytes: Optional[Int] = {},
        var ext_bits: Optional[Int] = {},
    ):
        self.int_kind = int_kind^
        self.size_bytes = size_bytes
        self.align_bytes = align_bytes^
        self.ext_bits = ext_bits^


struct FloatType(Copyable, Movable):
    var float_kind: FloatKind
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(
        out self,
        var float_kind: FloatKind,
        var size_bytes: Int,
        var align_bytes: Optional[Int] = {},
    ):
        self.float_kind = float_kind^
        self.size_bytes = size_bytes
        self.align_bytes = align_bytes^


struct QualifiedType(Copyable, Movable):
    var unqualified: ArcPointer[CType]
    var qualifiers: Qualifiers

    def __init__(
        out self, var unqualified: ArcPointer[CType], var qualifiers: Qualifiers = Qualifiers()
    ):
        self.unqualified = unqualified^
        self.qualifiers = qualifiers^


struct AtomicType(Copyable, Movable):
    var value_type: ArcPointer[CType]
    var size_bytes: Optional[Int]
    var align_bytes: Optional[Int]

    def __init__(
        out self,
        var value_type: ArcPointer[CType],
        var size_bytes: Optional[Int] = {},
        var align_bytes: Optional[Int] = {},
    ):
        self.value_type = value_type^
        self.size_bytes = size_bytes^
        self.align_bytes = align_bytes^


struct CPointer(Copyable, Movable):
    var pointee: Optional[ArcPointer[CType]]
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(
        out self,
        var pointee: Optional[ArcPointer[CType]],
        var size_bytes: Int = 0,
        var align_bytes: Optional[Int] = {},
    ):
        self.pointee = pointee^
        self.size_bytes = size_bytes
        self.align_bytes = align_bytes^


struct CArray(Copyable, Movable):
    var element: ArcPointer[CType]
    var size: Optional[Int]
    var array_kind: ArrayKind
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(
        out self,
        var element: ArcPointer[CType],
        var size: Optional[Int],
        var array_kind: ArrayKind = ArrayKind.fixed,
        var size_bytes: Int = 0,
        var align_bytes: Optional[Int] = {},
    ):
        self.element = element^
        self.size = size^
        self.array_kind = array_kind^
        self.size_bytes = size_bytes
        self.align_bytes = align_bytes^


struct CFunctionPtr(Copyable, Movable):
    var ret: ArcPointer[CType]
    var params: List[CParam]
    var param_names: Optional[List[String]]
    var is_variadic: Bool
    var calling_convention: Optional[String]
    var is_noreturn: Bool
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(
        out self,
        var ret: ArcPointer[CType],
        var params: List[CParam],
        var param_names: Optional[List[String]] = {},
        var is_variadic: Bool = False,
        var calling_convention: Optional[String] = {},
        var is_noreturn: Bool = False,
        var size_bytes: Int = 0,
        var align_bytes: Optional[Int] = {},
    ):
        self.ret = ret^
        self.params = params^
        self.param_names = param_names^
        self.is_variadic = is_variadic
        self.calling_convention = calling_convention^
        self.is_noreturn = is_noreturn
        self.size_bytes = size_bytes
        self.align_bytes = align_bytes^


struct OpaqueRecordRef(Copyable, Movable):
    var decl_id: String
    var name: String
    var c_name: String
    var is_union: Bool
    var size_bytes: Optional[Int]
    var align_bytes: Optional[Int]

    def __init__(
        out self,
        var decl_id: String,
        var name: String,
        var c_name: String,
        var is_union: Bool = False,
        var size_bytes: Optional[Int] = {},
        var align_bytes: Optional[Int] = {},
    ):
        self.decl_id = decl_id^
        self.name = name^
        self.c_name = c_name^
        self.is_union = is_union
        self.size_bytes = size_bytes^
        self.align_bytes = align_bytes^


struct UnsupportedType(Copyable, Movable):
    var category: UnsupportedTypeCategory
    var spelling: String
    var reason: String
    var size_bytes: Optional[Int]
    var align_bytes: Optional[Int]

    def __init__(
        out self,
        var category: UnsupportedTypeCategory,
        var spelling: String,
        var reason: String,
        var size_bytes: Optional[Int] = {},
        var align_bytes: Optional[Int] = {},
    ):
        self.category = category^
        self.spelling = spelling^
        self.reason = reason^
        self.size_bytes = size_bytes^
        self.align_bytes = align_bytes^


struct ComplexType(Copyable, Movable):
    var element: FloatType
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(
        out self, var element: FloatType, var size_bytes: Int, var align_bytes: Optional[Int] = {}
    ):
        self.element = element^
        self.size_bytes = size_bytes
        self.align_bytes = align_bytes^


struct VectorType(Copyable, Movable):
    var element: ArcPointer[CType]
    var count: Optional[Int]
    var size_bytes: Int
    var is_ext_vector: Bool
    var align_bytes: Optional[Int]

    def __init__(
        out self,
        var element: ArcPointer[CType],
        var count: Optional[Int],
        var size_bytes: Int,
        var is_ext_vector: Bool = False,
        var align_bytes: Optional[Int] = {},
    ):
        self.element = element^
        self.count = count^
        self.size_bytes = size_bytes
        self.is_ext_vector = is_ext_vector
        self.align_bytes = align_bytes^


struct StructRef(Copyable, Movable):
    var decl_id: String
    var name: String
    var c_name: String
    var is_union: Bool
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var is_anonymous: Bool

    def __init__(
        out self,
        var decl_id: String,
        var name: String,
        var c_name: String,
        var is_union: Bool = False,
        var size_bytes: Int = 0,
        var align_bytes: Optional[Int] = {},
        var is_anonymous: Bool = False,
    ):
        self.decl_id = decl_id^
        self.name = name^
        self.c_name = c_name^
        self.is_union = is_union
        self.size_bytes = size_bytes
        self.align_bytes = align_bytes^
        self.is_anonymous = is_anonymous


struct EnumRef(Copyable, Movable):
    var decl_id: String
    var name: String
    var c_name: String
    var underlying: IntType

    def __init__(
        out self, var decl_id: String, var name: String, var c_name: String, var underlying: IntType
    ):
        self.decl_id = decl_id^
        self.name = name^
        self.c_name = c_name^
        self.underlying = underlying^


struct TypeRef(Copyable, Movable):
    var decl_id: String
    var name: String
    var canonical: ArcPointer[CType]

    def __init__(out self, var decl_id: String, var name: String, var canonical: ArcPointer[CType]):
        self.decl_id = decl_id^
        self.name = name^
        self.canonical = canonical^


struct CParam(Copyable, Movable):
    var name: String
    var type: ArcPointer[CType]
    var doc: Optional[DocComment]

    def __init__(
        out self, var name: String, var type: ArcPointer[CType], var doc: Optional[DocComment] = {}
    ):
        self.name = name^
        self.type = type^
        self.doc = doc^


struct MojoParam(Copyable, Movable):
    var name: String
    var type: ArcPointer[MojoType]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var type: ArcPointer[MojoType],
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.type = type^
        self.doc = doc^


struct MojoPointer(Copyable, Movable):
    var pointee: Optional[ArcPointer[MojoType]]
    var mutability: PointerMutability
    var origin: PointerOrigin
    var nullable: Bool

    def __init__(
        out self,
        var pointee: Optional[ArcPointer[MojoType]],
        var mutability: PointerMutability = PointerMutability.MUT,
        var origin: PointerOrigin = PointerOrigin.EXTERNAL,
        var nullable: Bool = False,
    ):
        self.pointee = pointee^
        self.mutability = mutability^
        self.origin = origin^
        self.nullable = nullable


struct MojoArray(Copyable, Movable):
    var element: ArcPointer[MojoType]
    var size: Int

    def __init__(out self, var element: ArcPointer[MojoType], var size: Int):
        self.element = element^
        self.size = size


struct MojoFunctionPtr(Copyable, Movable):
    var ret: ArcPointer[MojoType]
    var params: List[MojoParam]
    var abi: String
    var thin: Bool
    var raises_error: Bool

    def __init__(
        out self,
        var ret: ArcPointer[MojoType],
        var params: List[MojoParam],
        var abi: String = "C",
        var thin: Bool = True,
        var raises_error: Bool = False,
    ):
        self.ret = ret^
        self.params = params^
        self.abi = abi^
        self.thin = thin
        self.raises_error = raises_error


struct BuiltinType(Copyable, Movable):
    var name: MojoBuiltin

    def __init__(out self, var name: MojoBuiltin):
        self.name = name^


struct NamedType(Copyable, Movable):
    var name: String

    def __init__(out self, var name: String):
        self.name = name^


struct DTypeArg(Copyable, Movable):
    var value: String

    def __init__(out self, var value: String):
        self.value = value^


struct ConstArg(Copyable, Movable):
    var value: Int

    def __init__(out self, var value: Int):
        self.value = value


struct NameArg(Copyable, Movable):
    var value: String

    def __init__(out self, var value: String):
        self.value = value^


struct TypeArg(Copyable, Movable):
    var type: ArcPointer[MojoType]

    def __init__(out self, var type: ArcPointer[MojoType]):
        self.type = type^


struct ParametricType(Copyable, Movable):
    var base: ParametricBase
    var args: List[ParametricArg]

    def __init__(
        out self, var base: ParametricBase, var args: List[ParametricArg] = List[ParametricArg]()
    ):
        self.base = base^
        self.args = args^


struct TargetABI(Copyable, Movable):
    var pointer_size_bytes: Int
    var pointer_align_bytes: Int
    var byte_order: ByteOrder
    var target_triple: Optional[String]

    def __init__(
        out self,
        var pointer_size_bytes: Int,
        var pointer_align_bytes: Int,
        var byte_order: ByteOrder,
        var target_triple: Optional[String] = {},
    ):
        self.pointer_size_bytes = pointer_size_bytes
        self.pointer_align_bytes = pointer_align_bytes
        self.byte_order = byte_order^
        self.target_triple = target_triple^


__enum CType(Copyable, Movable):
    case void_type(VoidType)
    case int_type(IntType)
    case float_type(FloatType)
    case qualified_type(QualifiedType)
    case atomic_type(AtomicType)
    case c_pointer(CPointer)
    case c_array(CArray)
    case c_function_ptr(CFunctionPtr)
    case opaque_record_ref(OpaqueRecordRef)
    case unsupported_type(UnsupportedType)
    case complex_type(ComplexType)
    case vector_type(VectorType)
    case struct_ref(StructRef)
    case enum_ref(EnumRef)
    case type_ref(TypeRef)

    def __deinit__(deinit self):
        # The pinned compiler needs this hook to resolve recursive lifecycle traits.
        pass


__enum MojoType(Copyable, Movable):
    case builtin_type(BuiltinType)
    case named_type(NamedType)
    case mojo_pointer(MojoPointer)
    case mojo_array(MojoArray)
    case mojo_function_ptr(MojoFunctionPtr)
    case parametric_type(ParametricType)

    def __deinit__(deinit self):
        # The pinned compiler needs this hook to resolve recursive lifecycle traits.
        pass


__enum ParametricArg(Copyable, Movable):
    case d_type_arg(DTypeArg)
    case const_arg(ConstArg)
    case name_arg(NameArg)
    case type_arg(TypeArg)

    def __deinit__(deinit self):
        # The pinned compiler needs this hook to resolve recursive lifecycle traits.
        pass

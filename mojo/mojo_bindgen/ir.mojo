"""Closed recursive CIR and MojoIR schemas; passes borrow published values."""

from std.memory import ArcPointer
from ._numbers import IntegerValue


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


__enum InlineDisposition(Equatable, ImplicitlyCopyable, Movable):
    case NONE
    case INLINE
    case EXTERN_INLINE

    def value(self) -> String:
        match self:
            case .NONE:
                return "none"
            case .INLINE:
                return "inline"
            case .EXTERN_INLINE:
                return "extern_inline"


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


__enum GlobalKind(Equatable, ImplicitlyCopyable, Movable):
    case WRAPPER
    case STUB

    def value(self) -> String:
        match self:
            case .WRAPPER:
                return "wrapper"
            case .STUB:
                return "stub"


__enum FunctionKind(Equatable, ImplicitlyCopyable, Movable):
    case WRAPPER
    case VARIADIC_STUB
    case DIRECTIVE_STUB
    case NON_REGISTER_RETURN_STUB

    def value(self) -> String:
        match self:
            case .WRAPPER:
                return "wrapper"
            case .VARIADIC_STUB:
                return "variadic_stub"
            case .DIRECTIVE_STUB:
                return "directive_stub"
            case .NON_REGISTER_RETURN_STUB:
                return "non_register_return_stub"


__enum LinkMode(Equatable, ImplicitlyCopyable, Movable):
    case EXTERNAL_CALL
    case OWNED_DL_HANDLE

    def value(self) -> String:
        match self:
            case .EXTERNAL_CALL:
                return "external_call"
            case .OWNED_DL_HANDLE:
                return "owned_dl_handle"


__enum MappingSeverity(Equatable, ImplicitlyCopyable, Movable):
    case NOTE
    case WARNING
    case ERROR

    def value(self) -> String:
        match self:
            case .NOTE:
                return "note"
            case .WARNING:
                return "warning"
            case .ERROR:
                return "error"


__enum SupportDeclKind(Equatable, ImplicitlyCopyable, Movable):
    case DL_HANDLE_HELPERS
    case GLOBAL_SYMBOL_HELPERS
    case VARIADIC_HELPERS

    def value(self) -> String:
        match self:
            case .DL_HANDLE_HELPERS:
                return "dl_handle_helpers"
            case .GLOBAL_SYMBOL_HELPERS:
                return "global_symbol_helpers"
            case .VARIADIC_HELPERS:
                return "variadic_helpers"


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


__enum StructTraits(Equatable, ImplicitlyCopyable, Movable):
    case NOT_MOVABLE
    case COPYABLE
    case IMPLICITLY_COPYABLE
    case MOVABLE
    case REGISTER_PASSABLE
    case TRIVIAL_REGISTER_PASSABLE

    def value(self) -> String:
        match self:
            case .NOT_MOVABLE:
                return "not Movable"
            case .COPYABLE:
                return "Copyable"
            case .IMPLICITLY_COPYABLE:
                return "ImplicitlyCopyable"
            case .MOVABLE:
                return "Movable"
            case .REGISTER_PASSABLE:
                return "RegisterPassable"
            case .TRIVIAL_REGISTER_PASSABLE:
                return "TrivialRegisterPassable"


__enum StructKind(Equatable, ImplicitlyCopyable, Movable):
    case PLAIN
    case OPAQUE

    def value(self) -> String:
        match self:
            case .PLAIN:
                return "plain"
            case .OPAQUE:
                return "opaque"


__enum MojoPassability(Equatable, ImplicitlyCopyable, Movable):
    case MEMORY_ONLY
    case REGISTER_PASSABLE
    case TRIVIAL_REGISTER_PASSABLE

    def value(self) -> String:
        match self:
            case .MEMORY_ONLY:
                return "memory_only"
            case .REGISTER_PASSABLE:
                return "register_passable"
            case .TRIVIAL_REGISTER_PASSABLE:
                return "trivial_register_passable"


__enum AliasKind(Equatable, ImplicitlyCopyable, Movable):
    case TYPE_ALIAS
    case CALLBACK_SIGNATURE
    case UNION_LAYOUT
    case CONST_VALUE
    case MACRO_VALUE

    def value(self) -> String:
        match self:
            case .TYPE_ALIAS:
                return "type_alias"
            case .CALLBACK_SIGNATURE:
                return "callback_signature"
            case .UNION_LAYOUT:
                return "union_layout"
            case .CONST_VALUE:
                return "const_value"
            case .MACRO_VALUE:
                return "macro_value"


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


__enum FamPattern(Equatable, ImplicitlyCopyable, Movable):
    case c99_empty
    case gnu_zero

    def value(self) -> String:
        match self:
            case .c99_empty:
                return "c99_empty"
            case .gnu_zero:
                return "gnu_zero"


__enum MacroDeclKind(Equatable, ImplicitlyCopyable, Movable):
    case object_like_supported
    case object_like_unsupported
    case function_like_unsupported
    case empty
    case predefined
    case invalid

    def value(self) -> String:
        match self:
            case .object_like_supported:
                return "object_like_supported"
            case .object_like_unsupported:
                return "object_like_unsupported"
            case .function_like_unsupported:
                return "function_like_unsupported"
            case .empty:
                return "empty"
            case .predefined:
                return "predefined"
            case .invalid:
                return "invalid"


__enum PrimitiveKind(Equatable, ImplicitlyCopyable, Movable):
    case int_kind(IntKind)
    case float_kind(FloatKind)

    def value(self) -> String:
        match self:
            case .int_kind(v):
                return v.value()
            case .float_kind(v):
                return v.value()


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


struct MojoArray(Copyable, Movable):
    var element: ArcPointer[MojoType]
    var size: Int

    def __init__(out self, var element: ArcPointer[MojoType], var size: Int):
        self.element = element^
        self.size = size


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


struct FunctionAttrs(Copyable, Movable):
    var inline_disposition: InlineDisposition
    var is_noreturn: Bool

    def __init__(
        out self,
        var inline_disposition: InlineDisposition = InlineDisposition.NONE,
        var is_noreturn: Bool = False,
    ):
        self.inline_disposition = inline_disposition^
        self.is_noreturn = is_noreturn


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


struct Field(Copyable, Movable):
    var name: String
    var source_name: String
    var type: ArcPointer[CType]
    var byte_offset: Int
    var size_bytes: Int
    var is_anonymous: Bool
    var is_bitfield: Bool
    var bit_offset: Int
    var bit_width: Int
    var fam_pattern: Optional[FamPattern]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var source_name: String,
        var type: ArcPointer[CType],
        var byte_offset: Int,
        var size_bytes: Int = 0,
        var is_anonymous: Bool = False,
        var is_bitfield: Bool = False,
        var bit_offset: Int = 0,
        var bit_width: Int = 0,
        var fam_pattern: Optional[FamPattern] = {},
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.source_name = source_name^
        self.type = type^
        self.byte_offset = byte_offset
        self.size_bytes = size_bytes
        self.is_anonymous = is_anonymous
        self.is_bitfield = is_bitfield
        self.bit_offset = bit_offset
        self.bit_width = bit_width
        self.fam_pattern = fam_pattern^
        self.doc = doc^


struct Struct(Copyable, Movable):
    var decl_id: String
    var name: String
    var c_name: String
    var fields: List[Field]
    var size_bytes: Int
    var align_bytes: Int
    var is_union: Bool
    var is_anonymous: Bool
    var is_complete: Bool
    var is_packed: Bool
    var requested_align_bytes: Optional[Int]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var decl_id: String,
        var name: String,
        var c_name: String,
        var fields: List[Field],
        var size_bytes: Int,
        var align_bytes: Int,
        var is_union: Bool = False,
        var is_anonymous: Bool = False,
        var is_complete: Bool = True,
        var is_packed: Bool = False,
        var requested_align_bytes: Optional[Int] = {},
        var doc: Optional[DocComment] = {},
    ):
        self.decl_id = decl_id^
        self.name = name^
        self.c_name = c_name^
        self.fields = fields^
        self.size_bytes = size_bytes
        self.align_bytes = align_bytes
        self.is_union = is_union
        self.is_anonymous = is_anonymous
        self.is_complete = is_complete
        self.is_packed = is_packed
        self.requested_align_bytes = requested_align_bytes^
        self.doc = doc^


struct IntLiteral(Copyable, Movable):
    var value: IntegerValue

    def __init__(out self, var value: IntegerValue):
        self.value = value^


struct CFloatLiteral(Copyable, Movable):
    var spelling: String

    def __init__(out self, var spelling: String):
        self.spelling = spelling^


struct MojoFloatLiteral(Copyable, Movable):
    var value: Float64

    def __init__(out self, var value: Float64):
        self.value = value


struct StringLiteral(Copyable, Movable):
    var value: String

    def __init__(out self, var value: String):
        self.value = value^


struct CharLiteral(Copyable, Movable):
    var value: String

    def __init__(out self, var value: String):
        self.value = value^


struct CNullPtrLiteral(Copyable, Movable):
    def __init__(out self):
        pass


struct CRefExpr(Copyable, Movable):
    var name: String

    def __init__(out self, var name: String):
        self.name = name^


struct MojoRefExpr(Copyable, Movable):
    var name: String

    def __init__(out self, var name: String):
        self.name = name^


struct CUnaryExpr(Copyable, Movable):
    var op: String
    var operand: ArcPointer[CConstExpr]

    def __init__(out self, var op: String, var operand: ArcPointer[CConstExpr]):
        self.op = op^
        self.operand = operand^


struct MojoUnaryExpr(Copyable, Movable):
    var op: String
    var operand: ArcPointer[MojoConstExpr]

    def __init__(out self, var op: String, var operand: ArcPointer[MojoConstExpr]):
        self.op = op^
        self.operand = operand^


struct CBinaryExpr(Copyable, Movable):
    var op: String
    var lhs: ArcPointer[CConstExpr]
    var rhs: ArcPointer[CConstExpr]

    def __init__(
        out self, var op: String, var lhs: ArcPointer[CConstExpr], var rhs: ArcPointer[CConstExpr]
    ):
        self.op = op^
        self.lhs = lhs^
        self.rhs = rhs^


struct MojoBinaryExpr(Copyable, Movable):
    var op: String
    var lhs: ArcPointer[MojoConstExpr]
    var rhs: ArcPointer[MojoConstExpr]

    def __init__(
        out self,
        var op: String,
        var lhs: ArcPointer[MojoConstExpr],
        var rhs: ArcPointer[MojoConstExpr],
    ):
        self.op = op^
        self.lhs = lhs^
        self.rhs = rhs^


struct CCastExpr(Copyable, Movable):
    var target: ArcPointer[CType]
    var expr: ArcPointer[CConstExpr]

    def __init__(out self, var target: ArcPointer[CType], var expr: ArcPointer[CConstExpr]):
        self.target = target^
        self.expr = expr^


struct MojoCastExpr(Copyable, Movable):
    var target: ArcPointer[MojoType]
    var expr: ArcPointer[MojoConstExpr]

    def __init__(out self, var target: ArcPointer[MojoType], var expr: ArcPointer[MojoConstExpr]):
        self.target = target^
        self.expr = expr^


struct CSizeOfExpr(Copyable, Movable):
    var target: ArcPointer[CType]

    def __init__(out self, var target: ArcPointer[CType]):
        self.target = target^


struct MojoSizeOfExpr(Copyable, Movable):
    var target: ArcPointer[MojoType]

    def __init__(out self, var target: ArcPointer[MojoType]):
        self.target = target^


struct CCallExpr(Copyable, Movable):
    var callee: ArcPointer[CConstExpr]
    var args: List[ArcPointer[CConstExpr]]

    def __init__(
        out self,
        var callee: ArcPointer[CConstExpr],
        var args: List[ArcPointer[CConstExpr]] = List[ArcPointer[CConstExpr]](),
    ):
        self.callee = callee^
        self.args = args^


struct MojoCallExpr(Copyable, Movable):
    var callee: ArcPointer[MojoConstExpr]
    var args: List[ArcPointer[MojoConstExpr]]

    def __init__(
        out self,
        var callee: ArcPointer[MojoConstExpr],
        var args: List[ArcPointer[MojoConstExpr]] = List[ArcPointer[MojoConstExpr]](),
    ):
        self.callee = callee^
        self.args = args^


struct Enumerant(Copyable, Movable):
    var name: String
    var c_name: String
    var value: IntegerValue
    var enum_decl_id: Optional[String]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var c_name: String,
        var value: IntegerValue,
        var enum_decl_id: Optional[String] = {},
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.c_name = c_name^
        self.value = value^
        self.enum_decl_id = enum_decl_id^
        self.doc = doc^


struct Enum(Copyable, Movable):
    var decl_id: String
    var name: String
    var c_name: String
    var underlying: IntType
    var enumerants: List[Enumerant]
    var alias_names: List[String]
    var is_anonymous: Bool
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var decl_id: String,
        var name: String,
        var c_name: String,
        var underlying: IntType,
        var enumerants: List[Enumerant],
        var alias_names: List[String] = List[String](),
        var is_anonymous: Bool = False,
        var doc: Optional[DocComment] = {},
    ):
        self.decl_id = decl_id^
        self.name = name^
        self.c_name = c_name^
        self.underlying = underlying^
        self.enumerants = enumerants^
        self.alias_names = alias_names^
        self.is_anonymous = is_anonymous
        self.doc = doc^


struct Typedef(Copyable, Movable):
    var decl_id: String
    var name: String
    var aliased: ArcPointer[CType]
    var canonical: ArcPointer[CType]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var decl_id: String,
        var name: String,
        var aliased: ArcPointer[CType],
        var canonical: ArcPointer[CType],
        var doc: Optional[DocComment] = {},
    ):
        self.decl_id = decl_id^
        self.name = name^
        self.aliased = aliased^
        self.canonical = canonical^
        self.doc = doc^


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


struct Function(Copyable, Movable):
    var name: String
    var link_name: String
    var ret: ArcPointer[CType]
    var params: List[CParam]
    var is_variadic: Bool
    var decl_id: String
    var calling_convention: Optional[String]
    var attrs: FunctionAttrs
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var link_name: String,
        var ret: ArcPointer[CType],
        var params: List[CParam],
        var is_variadic: Bool = False,
        var decl_id: String = "",
        var calling_convention: Optional[String] = {},
        var attrs: FunctionAttrs = FunctionAttrs(),
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.link_name = link_name^
        self.ret = ret^
        self.params = params^
        self.is_variadic = is_variadic
        self.decl_id = decl_id^
        self.calling_convention = calling_convention^
        self.attrs = attrs^
        self.doc = doc^


struct Const(Copyable, Movable):
    var name: String
    var type: ArcPointer[CType]
    var expr: ArcPointer[CConstExpr]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var type: ArcPointer[CType],
        var expr: ArcPointer[CConstExpr],
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.type = type^
        self.expr = expr^
        self.doc = doc^


struct MacroDecl(Copyable, Movable):
    var name: String
    var tokens: List[String]
    var kind: MacroDeclKind
    var expr: Optional[ArcPointer[CConstExpr]]
    var type: Optional[ArcPointer[CType]]
    var diagnostic: Optional[String]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var tokens: List[String],
        var kind: MacroDeclKind,
        var expr: Optional[ArcPointer[CConstExpr]] = {},
        var type: Optional[ArcPointer[CType]] = {},
        var diagnostic: Optional[String] = {},
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.tokens = tokens^
        self.kind = kind^
        self.expr = expr^
        self.type = type^
        self.diagnostic = diagnostic^
        self.doc = doc^


struct GlobalVar(Copyable, Movable):
    var decl_id: String
    var name: String
    var link_name: String
    var type: ArcPointer[CType]
    var is_const: Bool
    var initializer: Optional[ArcPointer[CConstExpr]]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var decl_id: String,
        var name: String,
        var link_name: String,
        var type: ArcPointer[CType],
        var is_const: Bool = False,
        var initializer: Optional[ArcPointer[CConstExpr]] = {},
        var doc: Optional[DocComment] = {},
    ):
        self.decl_id = decl_id^
        self.name = name^
        self.link_name = link_name^
        self.type = type^
        self.is_const = is_const
        self.initializer = initializer^
        self.doc = doc^


struct IRDiagnostic(Copyable, Movable):
    var severity: String
    var message: String
    var file: Optional[String]
    var line: Optional[Int]
    var col: Optional[Int]
    var decl_id: Optional[String]

    def __init__(
        out self,
        var severity: String,
        var message: String,
        var file: Optional[String] = {},
        var line: Optional[Int] = {},
        var col: Optional[Int] = {},
        var decl_id: Optional[String] = {},
    ):
        self.severity = severity^
        self.message = message^
        self.file = file^
        self.line = line^
        self.col = col^
        self.decl_id = decl_id^


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


struct Unit(Copyable, Movable):
    var source_header: String
    var library: String
    var link_name: String
    var target_abi: TargetABI
    var decls: List[Decl]
    var diagnostics: List[IRDiagnostic]

    def __init__(
        out self,
        var source_header: String,
        var library: String,
        var link_name: String,
        var target_abi: TargetABI,
        var decls: List[Decl] = List[Decl](),
        var diagnostics: List[IRDiagnostic] = List[IRDiagnostic](),
    ):
        self.source_header = source_header^
        self.library = library^
        self.link_name = link_name^
        self.target_abi = target_abi^
        self.decls = decls^
        self.diagnostics = diagnostics^


struct PrimitiveDType(Copyable, Movable):
    var kind: PrimitiveKind
    var signed: Bool
    var dtype: String
    var width_bytes: Int

    def __init__(
        out self, var kind: PrimitiveKind, var signed: Bool, var dtype: String, var width_bytes: Int
    ):
        self.kind = kind^
        self.signed = signed
        self.dtype = dtype^
        self.width_bytes = width_bytes


struct MappingNote(Copyable, Movable):
    var severity: MappingSeverity
    var message: String
    var category: String

    def __init__(
        out self, var severity: MappingSeverity, var message: String, var category: String
    ):
        self.severity = severity^
        self.message = message^
        self.category = category^


struct ModuleImport(Copyable, Movable):
    var module: String
    var names: List[String]

    def __init__(out self, var module: String, var names: List[String]):
        self.module = module^
        self.names = names^


struct SupportDecl(Copyable, Movable):
    var kind: SupportDeclKind

    def __init__(out self, var kind: SupportDeclKind):
        self.kind = kind^


struct ModuleDependencies(Copyable, Movable):
    var imports: List[ModuleImport]
    var support_decls: List[SupportDecl]

    def __init__(
        out self,
        var imports: List[ModuleImport] = List[ModuleImport](),
        var support_decls: List[SupportDecl] = List[SupportDecl](),
    ):
        self.imports = imports^
        self.support_decls = support_decls^


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
    var value: IntegerValue

    def __init__(out self, var value: IntegerValue):
        self.value = value^


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


struct StoredMember(Copyable, Movable):
    var index: Int
    var name: String
    var type: ArcPointer[MojoType]
    var byte_offset: Int
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var index: Int,
        var name: String,
        var type: ArcPointer[MojoType],
        var byte_offset: Int,
        var doc: Optional[DocComment] = {},
    ):
        self.index = index
        self.name = name^
        self.type = type^
        self.byte_offset = byte_offset
        self.doc = doc^


struct PaddingMember(Copyable, Movable):
    var name: String
    var size_bytes: Int
    var byte_offset: Int

    def __init__(out self, var name: String, var size_bytes: Int, var byte_offset: Int):
        self.name = name^
        self.size_bytes = size_bytes
        self.byte_offset = byte_offset


struct OpaqueStorageMember(Copyable, Movable):
    var name: String
    var size_bytes: Int

    def __init__(out self, var name: String, var size_bytes: Int):
        self.name = name^
        self.size_bytes = size_bytes


struct BitfieldField(Copyable, Movable):
    var index: Int
    var name: String
    var logical_type: ArcPointer[MojoType]
    var bit_offset: Int
    var bit_width: Int
    var signed: Bool
    var bool_semantics: Bool
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var index: Int,
        var name: String,
        var logical_type: ArcPointer[MojoType],
        var bit_offset: Int,
        var bit_width: Int,
        var signed: Bool,
        var bool_semantics: Bool = False,
        var doc: Optional[DocComment] = {},
    ):
        self.index = index
        self.name = name^
        self.logical_type = logical_type^
        self.bit_offset = bit_offset
        self.bit_width = bit_width
        self.signed = signed
        self.bool_semantics = bool_semantics
        self.doc = doc^


struct BitfieldGroupMember(Copyable, Movable):
    var storage_name: String
    var storage_type: ArcPointer[MojoType]
    var byte_offset: Int
    var first_index: Int
    var storage_width_bits: Int
    var fields: List[BitfieldField]

    def __init__(
        out self,
        var storage_name: String,
        var storage_type: ArcPointer[MojoType],
        var byte_offset: Int,
        var first_index: Int,
        var storage_width_bits: Int,
        var fields: List[BitfieldField] = List[BitfieldField](),
    ):
        self.storage_name = storage_name^
        self.storage_type = storage_type^
        self.byte_offset = byte_offset
        self.first_index = first_index
        self.storage_width_bits = storage_width_bits
        self.fields = fields^


struct ComptimeMember(Copyable, Movable):
    var name: String
    var type_value: Optional[ArcPointer[MojoType]]
    var const_value: Optional[ArcPointer[MojoConstExpr]]

    def __init__(
        out self,
        var name: String,
        var type_value: Optional[ArcPointer[MojoType]] = {},
        var const_value: Optional[ArcPointer[MojoConstExpr]] = {},
    ):
        self.name = name^
        self.type_value = type_value^
        self.const_value = const_value^


struct InitializerParam(Copyable, Movable):
    var name: String
    var type: ArcPointer[MojoType]

    def __init__(out self, var name: String, var type: ArcPointer[MojoType]):
        self.name = name^
        self.type = type^


struct Initializer(Copyable, Movable):
    var params: List[InitializerParam]

    def __init__(out self, var params: List[InitializerParam] = List[InitializerParam]()):
        self.params = params^


struct FlexibleTail(Copyable, Movable):
    var field_name: String
    var element_type: ArcPointer[MojoType]
    var pattern: String
    var byte_offset: Int

    def __init__(
        out self,
        var field_name: String,
        var element_type: ArcPointer[MojoType],
        var pattern: String,
        var byte_offset: Int,
    ):
        self.field_name = field_name^
        self.element_type = element_type^
        self.pattern = pattern^
        self.byte_offset = byte_offset


struct StructDecl(Copyable, Movable):
    var name: String
    var traits: List[StructTraits]
    var passability: MojoPassability
    var align: Optional[Int]
    var align_decorator: Optional[Int]
    var fieldwise_init: Bool
    var kind: StructKind
    var members: List[StructMember]
    var comptime_members: List[ComptimeMember]
    var initializers: List[Initializer]
    var flexible_tail: Optional[FlexibleTail]
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var traits: List[StructTraits] = List[StructTraits](),
        var passability: MojoPassability = MojoPassability.MEMORY_ONLY,
        var align: Optional[Int] = {},
        var align_decorator: Optional[Int] = {},
        var fieldwise_init: Bool = False,
        var kind: StructKind = StructKind.PLAIN,
        var members: List[StructMember] = List[StructMember](),
        var comptime_members: List[ComptimeMember] = List[ComptimeMember](),
        var initializers: List[Initializer] = List[Initializer](),
        var flexible_tail: Optional[FlexibleTail] = {},
        var diagnostics: List[MappingNote] = List[MappingNote](),
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.traits = traits^
        self.passability = passability^
        self.align = align^
        self.align_decorator = align_decorator^
        self.fieldwise_init = fieldwise_init
        self.kind = kind^
        self.members = members^
        self.comptime_members = comptime_members^
        self.initializers = initializers^
        self.flexible_tail = flexible_tail^
        self.diagnostics = diagnostics^
        self.doc = doc^


struct AliasDecl(Copyable, Movable):
    var name: String
    var kind: AliasKind
    var type_value: Optional[ArcPointer[MojoType]]
    var const_type: Optional[ArcPointer[MojoType]]
    var const_value: Optional[ArcPointer[MojoConstExpr]]
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var kind: AliasKind,
        var type_value: Optional[ArcPointer[MojoType]] = {},
        var const_type: Optional[ArcPointer[MojoType]] = {},
        var const_value: Optional[ArcPointer[MojoConstExpr]] = {},
        var diagnostics: List[MappingNote] = List[MappingNote](),
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.kind = kind^
        self.type_value = type_value^
        self.const_type = const_type^
        self.const_value = const_value^
        self.diagnostics = diagnostics^
        self.doc = doc^


struct CallTarget(Copyable, Movable):
    var link_mode: LinkMode
    var symbol: String

    def __init__(out self, var link_mode: LinkMode, var symbol: String):
        self.link_mode = link_mode^
        self.symbol = symbol^


struct FunctionDecl(Copyable, Movable):
    var name: String
    var link_name: String
    var params: List[MojoParam]
    var return_type: ArcPointer[MojoType]
    var kind: FunctionKind
    var call_target: CallTarget
    var attrs: FunctionAttrs
    var num_fixed_args: Optional[Int]
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var link_name: String,
        var params: List[MojoParam] = List[MojoParam](),
        var return_type: ArcPointer[MojoType] = ArcPointer(
            MojoType.builtin_type(BuiltinType(MojoBuiltin.NONE))
        ),
        var kind: FunctionKind = FunctionKind.WRAPPER,
        var call_target: CallTarget = CallTarget(LinkMode.EXTERNAL_CALL, ""),
        var attrs: FunctionAttrs = FunctionAttrs(),
        var num_fixed_args: Optional[Int] = {},
        var diagnostics: List[MappingNote] = List[MappingNote](),
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.link_name = link_name^
        self.params = params^
        self.return_type = return_type^
        self.kind = kind^
        self.call_target = call_target^
        self.attrs = attrs^
        self.num_fixed_args = num_fixed_args^
        self.diagnostics = diagnostics^
        self.doc = doc^


struct GlobalDecl(Copyable, Movable):
    var name: String
    var link_name: String
    var value_type: ArcPointer[MojoType]
    var is_const: Bool
    var kind: GlobalKind
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(
        out self,
        var name: String,
        var link_name: String,
        var value_type: ArcPointer[MojoType],
        var is_const: Bool = False,
        var kind: GlobalKind = GlobalKind.WRAPPER,
        var diagnostics: List[MappingNote] = List[MappingNote](),
        var doc: Optional[DocComment] = {},
    ):
        self.name = name^
        self.link_name = link_name^
        self.value_type = value_type^
        self.is_const = is_const
        self.kind = kind^
        self.diagnostics = diagnostics^
        self.doc = doc^


struct MojoModule(Copyable, Movable):
    var source_header: String
    var library: String
    var link_name: String
    var link_mode: LinkMode
    var library_path_hint: Optional[String]
    var dependencies: ModuleDependencies
    var decls: List[MojoDecl]

    def __init__(
        out self,
        var source_header: String,
        var library: String,
        var link_name: String,
        var link_mode: LinkMode,
        var library_path_hint: Optional[String] = {},
        var dependencies: ModuleDependencies = ModuleDependencies(),
        var decls: List[MojoDecl] = List[MojoDecl](),
    ):
        self.source_header = source_header^
        self.library = library^
        self.link_name = link_name^
        self.link_mode = link_mode^
        self.library_path_hint = library_path_hint^
        self.dependencies = dependencies^
        self.decls = decls^


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
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass


__enum MojoType(Copyable, Movable):
    case builtin_type(BuiltinType)
    case named_type(NamedType)
    case mojo_pointer(MojoPointer)
    case mojo_array(MojoArray)
    case mojo_function_ptr(MojoFunctionPtr)
    case parametric_type(ParametricType)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass


__enum ParametricArg(Copyable, Movable):
    case d_type_arg(DTypeArg)
    case const_arg(ConstArg)
    case name_arg(NameArg)
    case type_arg(TypeArg)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass


__enum CConstExpr(Copyable, Movable):
    case int_literal(IntLiteral)
    case c_float_literal(CFloatLiteral)
    case string_literal(StringLiteral)
    case char_literal(CharLiteral)
    case c_null_ptr_literal(CNullPtrLiteral)
    case c_ref_expr(CRefExpr)
    case c_unary_expr(CUnaryExpr)
    case c_binary_expr(CBinaryExpr)
    case c_cast_expr(CCastExpr)
    case c_size_of_expr(CSizeOfExpr)
    case c_call_expr(CCallExpr)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass


__enum MojoConstExpr(Copyable, Movable):
    case int_literal(IntLiteral)
    case mojo_float_literal(MojoFloatLiteral)
    case string_literal(StringLiteral)
    case char_literal(CharLiteral)
    case mojo_ref_expr(MojoRefExpr)
    case mojo_unary_expr(MojoUnaryExpr)
    case mojo_binary_expr(MojoBinaryExpr)
    case mojo_cast_expr(MojoCastExpr)
    case mojo_size_of_expr(MojoSizeOfExpr)
    case mojo_call_expr(MojoCallExpr)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass


__enum Decl(Copyable, Movable):
    case function(Function)
    case struct_decl(Struct)
    case enum_decl(Enum)
    case typedef(Typedef)
    case const_decl(Const)
    case macro_decl(MacroDecl)
    case global_var(GlobalVar)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass


__enum MojoDecl(Copyable, Movable):
    case struct_decl(StructDecl)
    case alias_decl(AliasDecl)
    case function_decl(FunctionDecl)
    case global_decl(GlobalDecl)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass


__enum StructMember(Copyable, Movable):
    case stored_member(StoredMember)
    case padding_member(PaddingMember)
    case opaque_storage_member(OpaqueStorageMember)
    case bitfield_group_member(BitfieldGroupMember)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass


def equal(a: ArcPointer[CConstExpr], b: ArcPointer[CConstExpr]) -> Bool:
    return equal(a.ptr()[], b.ptr()[])


def equal(a: ArcPointer[CType], b: ArcPointer[CType]) -> Bool:
    return equal(a.ptr()[], b.ptr()[])


def equal(a: ArcPointer[MojoConstExpr], b: ArcPointer[MojoConstExpr]) -> Bool:
    return equal(a.ptr()[], b.ptr()[])


def equal(a: ArcPointer[MojoType], b: ArcPointer[MojoType]) -> Bool:
    return equal(a.ptr()[], b.ptr()[])


def equal(a: List[ArcPointer[CConstExpr]], b: List[ArcPointer[CConstExpr]]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[ArcPointer[MojoConstExpr]], b: List[ArcPointer[MojoConstExpr]]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[BitfieldField], b: List[BitfieldField]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[CParam], b: List[CParam]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[ComptimeMember], b: List[ComptimeMember]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[Decl], b: List[Decl]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[Enumerant], b: List[Enumerant]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[Field], b: List[Field]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[IRDiagnostic], b: List[IRDiagnostic]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[InitializerParam], b: List[InitializerParam]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[Initializer], b: List[Initializer]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[MappingNote], b: List[MappingNote]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[ModuleImport], b: List[ModuleImport]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[MojoDecl], b: List[MojoDecl]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[MojoParam], b: List[MojoParam]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[ParametricArg], b: List[ParametricArg]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[String], b: List[String]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (a[i] == b[i]):
            return False
    return True


def equal(a: List[StructMember], b: List[StructMember]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: List[StructTraits], b: List[StructTraits]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (a[i] == b[i]):
            return False
    return True


def equal(a: List[SupportDecl], b: List[SupportDecl]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if not (equal(a[i], b[i])):
            return False
    return True


def equal(a: Optional[ArcPointer[CConstExpr]], b: Optional[ArcPointer[CConstExpr]]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return equal(a.value(), b.value())


def equal(a: Optional[ArcPointer[CType]], b: Optional[ArcPointer[CType]]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return equal(a.value(), b.value())


def equal(a: Optional[ArcPointer[MojoConstExpr]], b: Optional[ArcPointer[MojoConstExpr]]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return equal(a.value(), b.value())


def equal(a: Optional[ArcPointer[MojoType]], b: Optional[ArcPointer[MojoType]]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return equal(a.value(), b.value())


def equal(a: Optional[DocComment], b: Optional[DocComment]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return equal(a.value(), b.value())


def equal(a: Optional[FamPattern], b: Optional[FamPattern]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return a.value() == b.value()


def equal(a: Optional[FlexibleTail], b: Optional[FlexibleTail]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return equal(a.value(), b.value())


def equal(a: Optional[Int], b: Optional[Int]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return a.value() == b.value()


def equal(a: Optional[List[String]], b: Optional[List[String]]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return equal(a.value(), b.value())


def equal(a: Optional[String], b: Optional[String]) -> Bool:
    if Bool(a) != Bool(b):
        return False
    if not a:
        return True
    return a.value() == b.value()


def equal(a: DocComment, b: DocComment) -> Bool:
    return (a.text == b.text) and (equal(a.brief, b.brief)) and (a.source == b.source)


def equal(a: Qualifiers, b: Qualifiers) -> Bool:
    return (
        (a.is_const == b.is_const)
        and (a.is_volatile == b.is_volatile)
        and (a.is_restrict == b.is_restrict)
    )


def equal(a: VoidType, b: VoidType) -> Bool:
    return True


def equal(a: IntType, b: IntType) -> Bool:
    return (
        (a.int_kind == b.int_kind)
        and (a.size_bytes == b.size_bytes)
        and (equal(a.align_bytes, b.align_bytes))
        and (equal(a.ext_bits, b.ext_bits))
    )


def equal(a: FloatType, b: FloatType) -> Bool:
    return (
        (a.float_kind == b.float_kind)
        and (a.size_bytes == b.size_bytes)
        and (equal(a.align_bytes, b.align_bytes))
    )


def equal(a: QualifiedType, b: QualifiedType) -> Bool:
    return (equal(a.unqualified, b.unqualified)) and (equal(a.qualifiers, b.qualifiers))


def equal(a: AtomicType, b: AtomicType) -> Bool:
    return (
        (equal(a.value_type, b.value_type))
        and (equal(a.size_bytes, b.size_bytes))
        and (equal(a.align_bytes, b.align_bytes))
    )


def equal(a: CPointer, b: CPointer) -> Bool:
    return (
        (equal(a.pointee, b.pointee))
        and (a.size_bytes == b.size_bytes)
        and (equal(a.align_bytes, b.align_bytes))
    )


def equal(a: MojoPointer, b: MojoPointer) -> Bool:
    return (
        (equal(a.pointee, b.pointee))
        and (a.mutability == b.mutability)
        and (a.origin == b.origin)
        and (a.nullable == b.nullable)
    )


def equal(a: CArray, b: CArray) -> Bool:
    return (
        (equal(a.element, b.element))
        and (equal(a.size, b.size))
        and (a.array_kind == b.array_kind)
        and (a.size_bytes == b.size_bytes)
        and (equal(a.align_bytes, b.align_bytes))
    )


def equal(a: MojoArray, b: MojoArray) -> Bool:
    return (equal(a.element, b.element)) and (a.size == b.size)


def equal(a: CFunctionPtr, b: CFunctionPtr) -> Bool:
    return (
        (equal(a.ret, b.ret))
        and (equal(a.params, b.params))
        and (equal(a.param_names, b.param_names))
        and (a.is_variadic == b.is_variadic)
        and (equal(a.calling_convention, b.calling_convention))
        and (a.is_noreturn == b.is_noreturn)
        and (a.size_bytes == b.size_bytes)
        and (equal(a.align_bytes, b.align_bytes))
    )


def equal(a: MojoFunctionPtr, b: MojoFunctionPtr) -> Bool:
    return (
        (equal(a.ret, b.ret))
        and (equal(a.params, b.params))
        and (a.abi == b.abi)
        and (a.thin == b.thin)
        and (a.raises_error == b.raises_error)
    )


def equal(a: FunctionAttrs, b: FunctionAttrs) -> Bool:
    return (a.inline_disposition == b.inline_disposition) and (a.is_noreturn == b.is_noreturn)


def equal(a: OpaqueRecordRef, b: OpaqueRecordRef) -> Bool:
    return (
        (a.decl_id == b.decl_id)
        and (a.name == b.name)
        and (a.c_name == b.c_name)
        and (a.is_union == b.is_union)
        and (equal(a.size_bytes, b.size_bytes))
        and (equal(a.align_bytes, b.align_bytes))
    )


def equal(a: UnsupportedType, b: UnsupportedType) -> Bool:
    return (
        (a.category == b.category)
        and (a.spelling == b.spelling)
        and (a.reason == b.reason)
        and (equal(a.size_bytes, b.size_bytes))
        and (equal(a.align_bytes, b.align_bytes))
    )


def equal(a: ComplexType, b: ComplexType) -> Bool:
    return (
        (equal(a.element, b.element))
        and (a.size_bytes == b.size_bytes)
        and (equal(a.align_bytes, b.align_bytes))
    )


def equal(a: VectorType, b: VectorType) -> Bool:
    return (
        (equal(a.element, b.element))
        and (equal(a.count, b.count))
        and (a.size_bytes == b.size_bytes)
        and (a.is_ext_vector == b.is_ext_vector)
        and (equal(a.align_bytes, b.align_bytes))
    )


def equal(a: StructRef, b: StructRef) -> Bool:
    return (
        (a.decl_id == b.decl_id)
        and (a.name == b.name)
        and (a.c_name == b.c_name)
        and (a.is_union == b.is_union)
        and (a.size_bytes == b.size_bytes)
        and (equal(a.align_bytes, b.align_bytes))
        and (a.is_anonymous == b.is_anonymous)
    )


def equal(a: EnumRef, b: EnumRef) -> Bool:
    return (
        (a.decl_id == b.decl_id)
        and (a.name == b.name)
        and (a.c_name == b.c_name)
        and (equal(a.underlying, b.underlying))
    )


def equal(a: TypeRef, b: TypeRef) -> Bool:
    return (a.decl_id == b.decl_id) and (a.name == b.name) and (equal(a.canonical, b.canonical))


def equal(a: Field, b: Field) -> Bool:
    return (
        (a.name == b.name)
        and (a.source_name == b.source_name)
        and (equal(a.type, b.type))
        and (a.byte_offset == b.byte_offset)
        and (a.size_bytes == b.size_bytes)
        and (a.is_anonymous == b.is_anonymous)
        and (a.is_bitfield == b.is_bitfield)
        and (a.bit_offset == b.bit_offset)
        and (a.bit_width == b.bit_width)
        and (equal(a.fam_pattern, b.fam_pattern))
        and (equal(a.doc, b.doc))
    )


def equal(a: Struct, b: Struct) -> Bool:
    return (
        (a.decl_id == b.decl_id)
        and (a.name == b.name)
        and (a.c_name == b.c_name)
        and (equal(a.fields, b.fields))
        and (a.size_bytes == b.size_bytes)
        and (a.align_bytes == b.align_bytes)
        and (a.is_union == b.is_union)
        and (a.is_anonymous == b.is_anonymous)
        and (a.is_complete == b.is_complete)
        and (a.is_packed == b.is_packed)
        and (equal(a.requested_align_bytes, b.requested_align_bytes))
        and (equal(a.doc, b.doc))
    )


def equal(a: IntLiteral, b: IntLiteral) -> Bool:
    return a.value == b.value


def equal(a: CFloatLiteral, b: CFloatLiteral) -> Bool:
    return a.spelling == b.spelling


def equal(a: MojoFloatLiteral, b: MojoFloatLiteral) -> Bool:
    return a.value == b.value


def equal(a: StringLiteral, b: StringLiteral) -> Bool:
    return a.value == b.value


def equal(a: CharLiteral, b: CharLiteral) -> Bool:
    return a.value == b.value


def equal(a: CNullPtrLiteral, b: CNullPtrLiteral) -> Bool:
    return True


def equal(a: CRefExpr, b: CRefExpr) -> Bool:
    return a.name == b.name


def equal(a: MojoRefExpr, b: MojoRefExpr) -> Bool:
    return a.name == b.name


def equal(a: CUnaryExpr, b: CUnaryExpr) -> Bool:
    return (a.op == b.op) and (equal(a.operand, b.operand))


def equal(a: MojoUnaryExpr, b: MojoUnaryExpr) -> Bool:
    return (a.op == b.op) and (equal(a.operand, b.operand))


def equal(a: CBinaryExpr, b: CBinaryExpr) -> Bool:
    return (a.op == b.op) and (equal(a.lhs, b.lhs)) and (equal(a.rhs, b.rhs))


def equal(a: MojoBinaryExpr, b: MojoBinaryExpr) -> Bool:
    return (a.op == b.op) and (equal(a.lhs, b.lhs)) and (equal(a.rhs, b.rhs))


def equal(a: CCastExpr, b: CCastExpr) -> Bool:
    return (equal(a.target, b.target)) and (equal(a.expr, b.expr))


def equal(a: MojoCastExpr, b: MojoCastExpr) -> Bool:
    return (equal(a.target, b.target)) and (equal(a.expr, b.expr))


def equal(a: CSizeOfExpr, b: CSizeOfExpr) -> Bool:
    return equal(a.target, b.target)


def equal(a: MojoSizeOfExpr, b: MojoSizeOfExpr) -> Bool:
    return equal(a.target, b.target)


def equal(a: CCallExpr, b: CCallExpr) -> Bool:
    return (equal(a.callee, b.callee)) and (equal(a.args, b.args))


def equal(a: MojoCallExpr, b: MojoCallExpr) -> Bool:
    return (equal(a.callee, b.callee)) and (equal(a.args, b.args))


def equal(a: Enumerant, b: Enumerant) -> Bool:
    return (
        (a.name == b.name)
        and (a.c_name == b.c_name)
        and (a.value == b.value)
        and (equal(a.enum_decl_id, b.enum_decl_id))
        and (equal(a.doc, b.doc))
    )


def equal(a: Enum, b: Enum) -> Bool:
    return (
        (a.decl_id == b.decl_id)
        and (a.name == b.name)
        and (a.c_name == b.c_name)
        and (equal(a.underlying, b.underlying))
        and (equal(a.enumerants, b.enumerants))
        and (equal(a.alias_names, b.alias_names))
        and (a.is_anonymous == b.is_anonymous)
        and (equal(a.doc, b.doc))
    )


def equal(a: Typedef, b: Typedef) -> Bool:
    return (
        (a.decl_id == b.decl_id)
        and (a.name == b.name)
        and (equal(a.aliased, b.aliased))
        and (equal(a.canonical, b.canonical))
        and (equal(a.doc, b.doc))
    )


def equal(a: CParam, b: CParam) -> Bool:
    return (a.name == b.name) and (equal(a.type, b.type)) and (equal(a.doc, b.doc))


def equal(a: MojoParam, b: MojoParam) -> Bool:
    return (a.name == b.name) and (equal(a.type, b.type)) and (equal(a.doc, b.doc))


def equal(a: Function, b: Function) -> Bool:
    return (
        (a.name == b.name)
        and (a.link_name == b.link_name)
        and (equal(a.ret, b.ret))
        and (equal(a.params, b.params))
        and (a.is_variadic == b.is_variadic)
        and (a.decl_id == b.decl_id)
        and (equal(a.calling_convention, b.calling_convention))
        and (equal(a.attrs, b.attrs))
        and (equal(a.doc, b.doc))
    )


def equal(a: Const, b: Const) -> Bool:
    return (
        (a.name == b.name)
        and (equal(a.type, b.type))
        and (equal(a.expr, b.expr))
        and (equal(a.doc, b.doc))
    )


def equal(a: MacroDecl, b: MacroDecl) -> Bool:
    return (
        (a.name == b.name)
        and (equal(a.tokens, b.tokens))
        and (a.kind == b.kind)
        and (equal(a.expr, b.expr))
        and (equal(a.type, b.type))
        and (equal(a.diagnostic, b.diagnostic))
        and (equal(a.doc, b.doc))
    )


def equal(a: GlobalVar, b: GlobalVar) -> Bool:
    return (
        (a.decl_id == b.decl_id)
        and (a.name == b.name)
        and (a.link_name == b.link_name)
        and (equal(a.type, b.type))
        and (a.is_const == b.is_const)
        and (equal(a.initializer, b.initializer))
        and (equal(a.doc, b.doc))
    )


def equal(a: IRDiagnostic, b: IRDiagnostic) -> Bool:
    return (
        (a.severity == b.severity)
        and (a.message == b.message)
        and (equal(a.file, b.file))
        and (equal(a.line, b.line))
        and (equal(a.col, b.col))
        and (equal(a.decl_id, b.decl_id))
    )


def equal(a: TargetABI, b: TargetABI) -> Bool:
    return (
        (a.pointer_size_bytes == b.pointer_size_bytes)
        and (a.pointer_align_bytes == b.pointer_align_bytes)
        and (a.byte_order == b.byte_order)
        and (equal(a.target_triple, b.target_triple))
    )


def equal(a: Unit, b: Unit) -> Bool:
    return (
        (a.source_header == b.source_header)
        and (a.library == b.library)
        and (a.link_name == b.link_name)
        and (equal(a.target_abi, b.target_abi))
        and (equal(a.decls, b.decls))
        and (equal(a.diagnostics, b.diagnostics))
    )


def equal(a: PrimitiveDType, b: PrimitiveDType) -> Bool:
    return (
        (a.kind == b.kind)
        and (a.signed == b.signed)
        and (a.dtype == b.dtype)
        and (a.width_bytes == b.width_bytes)
    )


def equal(a: MappingNote, b: MappingNote) -> Bool:
    return (a.severity == b.severity) and (a.message == b.message) and (a.category == b.category)


def equal(a: ModuleImport, b: ModuleImport) -> Bool:
    return (a.module == b.module) and (equal(a.names, b.names))


def equal(a: SupportDecl, b: SupportDecl) -> Bool:
    return a.kind == b.kind


def equal(a: ModuleDependencies, b: ModuleDependencies) -> Bool:
    return (equal(a.imports, b.imports)) and (equal(a.support_decls, b.support_decls))


def equal(a: BuiltinType, b: BuiltinType) -> Bool:
    return a.name == b.name


def equal(a: NamedType, b: NamedType) -> Bool:
    return a.name == b.name


def equal(a: DTypeArg, b: DTypeArg) -> Bool:
    return a.value == b.value


def equal(a: ConstArg, b: ConstArg) -> Bool:
    return a.value == b.value


def equal(a: NameArg, b: NameArg) -> Bool:
    return a.value == b.value


def equal(a: TypeArg, b: TypeArg) -> Bool:
    return equal(a.type, b.type)


def equal(a: ParametricType, b: ParametricType) -> Bool:
    return (a.base == b.base) and (equal(a.args, b.args))


def equal(a: StoredMember, b: StoredMember) -> Bool:
    return (
        (a.index == b.index)
        and (a.name == b.name)
        and (equal(a.type, b.type))
        and (a.byte_offset == b.byte_offset)
        and (equal(a.doc, b.doc))
    )


def equal(a: PaddingMember, b: PaddingMember) -> Bool:
    return (
        (a.name == b.name) and (a.size_bytes == b.size_bytes) and (a.byte_offset == b.byte_offset)
    )


def equal(a: OpaqueStorageMember, b: OpaqueStorageMember) -> Bool:
    return (a.name == b.name) and (a.size_bytes == b.size_bytes)


def equal(a: BitfieldField, b: BitfieldField) -> Bool:
    return (
        (a.index == b.index)
        and (a.name == b.name)
        and (equal(a.logical_type, b.logical_type))
        and (a.bit_offset == b.bit_offset)
        and (a.bit_width == b.bit_width)
        and (a.signed == b.signed)
        and (a.bool_semantics == b.bool_semantics)
        and (equal(a.doc, b.doc))
    )


def equal(a: BitfieldGroupMember, b: BitfieldGroupMember) -> Bool:
    return (
        (a.storage_name == b.storage_name)
        and (equal(a.storage_type, b.storage_type))
        and (a.byte_offset == b.byte_offset)
        and (a.first_index == b.first_index)
        and (a.storage_width_bits == b.storage_width_bits)
        and (equal(a.fields, b.fields))
    )


def equal(a: ComptimeMember, b: ComptimeMember) -> Bool:
    return (
        (a.name == b.name)
        and (equal(a.type_value, b.type_value))
        and (equal(a.const_value, b.const_value))
    )


def equal(a: InitializerParam, b: InitializerParam) -> Bool:
    return (a.name == b.name) and (equal(a.type, b.type))


def equal(a: Initializer, b: Initializer) -> Bool:
    return equal(a.params, b.params)


def equal(a: FlexibleTail, b: FlexibleTail) -> Bool:
    return (
        (a.field_name == b.field_name)
        and (equal(a.element_type, b.element_type))
        and (a.pattern == b.pattern)
        and (a.byte_offset == b.byte_offset)
    )


def equal(a: StructDecl, b: StructDecl) -> Bool:
    return (
        (a.name == b.name)
        and (equal(a.traits, b.traits))
        and (a.passability == b.passability)
        and (equal(a.align, b.align))
        and (equal(a.align_decorator, b.align_decorator))
        and (a.fieldwise_init == b.fieldwise_init)
        and (a.kind == b.kind)
        and (equal(a.members, b.members))
        and (equal(a.comptime_members, b.comptime_members))
        and (equal(a.initializers, b.initializers))
        and (equal(a.flexible_tail, b.flexible_tail))
        and (equal(a.diagnostics, b.diagnostics))
        and (equal(a.doc, b.doc))
    )


def equal(a: AliasDecl, b: AliasDecl) -> Bool:
    return (
        (a.name == b.name)
        and (a.kind == b.kind)
        and (equal(a.type_value, b.type_value))
        and (equal(a.const_type, b.const_type))
        and (equal(a.const_value, b.const_value))
        and (equal(a.diagnostics, b.diagnostics))
        and (equal(a.doc, b.doc))
    )


def equal(a: CallTarget, b: CallTarget) -> Bool:
    return (a.link_mode == b.link_mode) and (a.symbol == b.symbol)


def equal(a: FunctionDecl, b: FunctionDecl) -> Bool:
    return (
        (a.name == b.name)
        and (a.link_name == b.link_name)
        and (equal(a.params, b.params))
        and (equal(a.return_type, b.return_type))
        and (a.kind == b.kind)
        and (equal(a.call_target, b.call_target))
        and (equal(a.attrs, b.attrs))
        and (equal(a.num_fixed_args, b.num_fixed_args))
        and (equal(a.diagnostics, b.diagnostics))
        and (equal(a.doc, b.doc))
    )


def equal(a: GlobalDecl, b: GlobalDecl) -> Bool:
    return (
        (a.name == b.name)
        and (a.link_name == b.link_name)
        and (equal(a.value_type, b.value_type))
        and (a.is_const == b.is_const)
        and (a.kind == b.kind)
        and (equal(a.diagnostics, b.diagnostics))
        and (equal(a.doc, b.doc))
    )


def equal(a: MojoModule, b: MojoModule) -> Bool:
    return (
        (a.source_header == b.source_header)
        and (a.library == b.library)
        and (a.link_name == b.link_name)
        and (a.link_mode == b.link_mode)
        and (equal(a.library_path_hint, b.library_path_hint))
        and (equal(a.dependencies, b.dependencies))
        and (equal(a.decls, b.decls))
    )


def equal(a: CType, b: CType) -> Bool:
    match a:
        case .void_type(av):
            match b:
                case .void_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .int_type(av):
            match b:
                case .int_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .float_type(av):
            match b:
                case .float_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .qualified_type(av):
            match b:
                case .qualified_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .atomic_type(av):
            match b:
                case .atomic_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_pointer(av):
            match b:
                case .c_pointer(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_array(av):
            match b:
                case .c_array(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_function_ptr(av):
            match b:
                case .c_function_ptr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .opaque_record_ref(av):
            match b:
                case .opaque_record_ref(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .unsupported_type(av):
            match b:
                case .unsupported_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .complex_type(av):
            match b:
                case .complex_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .vector_type(av):
            match b:
                case .vector_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .struct_ref(av):
            match b:
                case .struct_ref(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .enum_ref(av):
            match b:
                case .enum_ref(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .type_ref(av):
            match b:
                case .type_ref(bv):
                    return equal(av, bv)
                case _:
                    return False


def equal(a: MojoType, b: MojoType) -> Bool:
    match a:
        case .builtin_type(av):
            match b:
                case .builtin_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .named_type(av):
            match b:
                case .named_type(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_pointer(av):
            match b:
                case .mojo_pointer(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_array(av):
            match b:
                case .mojo_array(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_function_ptr(av):
            match b:
                case .mojo_function_ptr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .parametric_type(av):
            match b:
                case .parametric_type(bv):
                    return equal(av, bv)
                case _:
                    return False


def equal(a: ParametricArg, b: ParametricArg) -> Bool:
    match a:
        case .d_type_arg(av):
            match b:
                case .d_type_arg(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .const_arg(av):
            match b:
                case .const_arg(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .name_arg(av):
            match b:
                case .name_arg(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .type_arg(av):
            match b:
                case .type_arg(bv):
                    return equal(av, bv)
                case _:
                    return False


def equal(a: CConstExpr, b: CConstExpr) -> Bool:
    match a:
        case .int_literal(av):
            match b:
                case .int_literal(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_float_literal(av):
            match b:
                case .c_float_literal(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .string_literal(av):
            match b:
                case .string_literal(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .char_literal(av):
            match b:
                case .char_literal(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_null_ptr_literal(av):
            match b:
                case .c_null_ptr_literal(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_ref_expr(av):
            match b:
                case .c_ref_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_unary_expr(av):
            match b:
                case .c_unary_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_binary_expr(av):
            match b:
                case .c_binary_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_cast_expr(av):
            match b:
                case .c_cast_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_size_of_expr(av):
            match b:
                case .c_size_of_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .c_call_expr(av):
            match b:
                case .c_call_expr(bv):
                    return equal(av, bv)
                case _:
                    return False


def equal(a: MojoConstExpr, b: MojoConstExpr) -> Bool:
    match a:
        case .int_literal(av):
            match b:
                case .int_literal(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_float_literal(av):
            match b:
                case .mojo_float_literal(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .string_literal(av):
            match b:
                case .string_literal(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .char_literal(av):
            match b:
                case .char_literal(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_ref_expr(av):
            match b:
                case .mojo_ref_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_unary_expr(av):
            match b:
                case .mojo_unary_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_binary_expr(av):
            match b:
                case .mojo_binary_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_cast_expr(av):
            match b:
                case .mojo_cast_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_size_of_expr(av):
            match b:
                case .mojo_size_of_expr(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .mojo_call_expr(av):
            match b:
                case .mojo_call_expr(bv):
                    return equal(av, bv)
                case _:
                    return False


def equal(a: Decl, b: Decl) -> Bool:
    match a:
        case .function(av):
            match b:
                case .function(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .struct_decl(av):
            match b:
                case .struct_decl(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .enum_decl(av):
            match b:
                case .enum_decl(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .typedef(av):
            match b:
                case .typedef(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .const_decl(av):
            match b:
                case .const_decl(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .macro_decl(av):
            match b:
                case .macro_decl(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .global_var(av):
            match b:
                case .global_var(bv):
                    return equal(av, bv)
                case _:
                    return False


def equal(a: MojoDecl, b: MojoDecl) -> Bool:
    match a:
        case .struct_decl(av):
            match b:
                case .struct_decl(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .alias_decl(av):
            match b:
                case .alias_decl(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .function_decl(av):
            match b:
                case .function_decl(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .global_decl(av):
            match b:
                case .global_decl(bv):
                    return equal(av, bv)
                case _:
                    return False


def equal(a: StructMember, b: StructMember) -> Bool:
    match a:
        case .stored_member(av):
            match b:
                case .stored_member(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .padding_member(av):
            match b:
                case .padding_member(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .opaque_storage_member(av):
            match b:
                case .opaque_storage_member(bv):
                    return equal(av, bv)
                case _:
                    return False
        case .bitfield_group_member(av):
            match b:
                case .bitfield_group_member(bv):
                    return equal(av, bv)
                case _:
                    return False

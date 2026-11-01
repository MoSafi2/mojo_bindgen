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
    case EXTERN_DECLARATION
    case VARIADIC_STUB
    case DIRECTIVE_STUB
    case NON_REGISTER_RETURN_STUB

    def value(self) -> String:
        match self:
            case .WRAPPER:
                return "wrapper"
            case .EXTERN_DECLARATION:
                return "extern_declaration"
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


struct DocComment(Copyable, Equatable, Movable):
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


struct Qualifiers(Copyable, Equatable, Movable):
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


struct VoidType(Copyable, Equatable, Movable):
    def __init__(out self):
        pass


struct IntType(Copyable, Equatable, Movable):
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


struct FloatType(Copyable, Equatable, Movable):
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


struct QualifiedType(Copyable, Equatable, Movable):
    var unqualified: ArcPointer[CType]
    var qualifiers: Qualifiers

    def __init__(
        out self, var unqualified: ArcPointer[CType], var qualifiers: Qualifiers = Qualifiers()
    ):
        self.unqualified = unqualified^
        self.qualifiers = qualifiers^


struct AtomicType(Copyable, Equatable, Movable):
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


struct CPointer(Copyable, Equatable, Movable):
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


struct MojoPointer(Copyable, Equatable, Movable):
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


struct CArray(Copyable, Equatable, Movable):
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


struct MojoArray(Copyable, Equatable, Movable):
    var element: ArcPointer[MojoType]
    var size: Int

    def __init__(out self, var element: ArcPointer[MojoType], var size: Int):
        self.element = element^
        self.size = size


struct CFunctionPtr(Copyable, Equatable, Movable):
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


struct MojoFunctionPtr(Copyable, Equatable, Movable):
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


struct FunctionAttrs(Copyable, Equatable, Movable):
    var inline_disposition: InlineDisposition
    var is_noreturn: Bool

    def __init__(
        out self,
        var inline_disposition: InlineDisposition = InlineDisposition.NONE,
        var is_noreturn: Bool = False,
    ):
        self.inline_disposition = inline_disposition^
        self.is_noreturn = is_noreturn


struct OpaqueRecordRef(Copyable, Equatable, Movable):
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


struct UnsupportedType(Copyable, Equatable, Movable):
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


struct ComplexType(Copyable, Equatable, Movable):
    var element: FloatType
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(
        out self, var element: FloatType, var size_bytes: Int, var align_bytes: Optional[Int] = {}
    ):
        self.element = element^
        self.size_bytes = size_bytes
        self.align_bytes = align_bytes^


struct VectorType(Copyable, Equatable, Movable):
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


struct StructRef(Copyable, Equatable, Movable):
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


struct EnumRef(Copyable, Equatable, Movable):
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


struct TypeRef(Copyable, Equatable, Movable):
    var decl_id: String
    var name: String
    var canonical: ArcPointer[CType]

    def __init__(out self, var decl_id: String, var name: String, var canonical: ArcPointer[CType]):
        self.decl_id = decl_id^
        self.name = name^
        self.canonical = canonical^


struct Field(Copyable, Equatable, Movable):
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


struct Struct(Copyable, Equatable, Movable):
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


struct IntLiteral(Copyable, Equatable, Movable):
    var value: IntegerValue

    def __init__(out self, var value: IntegerValue):
        self.value = value^


struct CFloatLiteral(Copyable, Equatable, Movable):
    var spelling: String

    def __init__(out self, var spelling: String):
        self.spelling = spelling^


struct MojoFloatLiteral(Copyable, Equatable, Movable):
    var value: Float64

    def __init__(out self, var value: Float64):
        self.value = value


struct StringLiteral(Copyable, Equatable, Movable):
    var value: String

    def __init__(out self, var value: String):
        self.value = value^


struct CharLiteral(Copyable, Equatable, Movable):
    var value: String

    def __init__(out self, var value: String):
        self.value = value^


struct CNullPtrLiteral(Copyable, Equatable, Movable):
    def __init__(out self):
        pass


struct CRefExpr(Copyable, Equatable, Movable):
    var name: String

    def __init__(out self, var name: String):
        self.name = name^


struct MojoRefExpr(Copyable, Equatable, Movable):
    var name: String

    def __init__(out self, var name: String):
        self.name = name^


struct CUnaryExpr(Copyable, Equatable, Movable):
    var op: String
    var operand: ArcPointer[CConstExpr]

    def __init__(out self, var op: String, var operand: ArcPointer[CConstExpr]):
        self.op = op^
        self.operand = operand^


struct MojoUnaryExpr(Copyable, Equatable, Movable):
    var op: String
    var operand: ArcPointer[MojoConstExpr]

    def __init__(out self, var op: String, var operand: ArcPointer[MojoConstExpr]):
        self.op = op^
        self.operand = operand^


struct CBinaryExpr(Copyable, Equatable, Movable):
    var op: String
    var lhs: ArcPointer[CConstExpr]
    var rhs: ArcPointer[CConstExpr]

    def __init__(
        out self, var op: String, var lhs: ArcPointer[CConstExpr], var rhs: ArcPointer[CConstExpr]
    ):
        self.op = op^
        self.lhs = lhs^
        self.rhs = rhs^


struct MojoBinaryExpr(Copyable, Equatable, Movable):
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


struct CCastExpr(Copyable, Equatable, Movable):
    var target: ArcPointer[CType]
    var expr: ArcPointer[CConstExpr]

    def __init__(out self, var target: ArcPointer[CType], var expr: ArcPointer[CConstExpr]):
        self.target = target^
        self.expr = expr^


struct MojoCastExpr(Copyable, Equatable, Movable):
    var target: ArcPointer[MojoType]
    var expr: ArcPointer[MojoConstExpr]

    def __init__(out self, var target: ArcPointer[MojoType], var expr: ArcPointer[MojoConstExpr]):
        self.target = target^
        self.expr = expr^


struct CSizeOfExpr(Copyable, Equatable, Movable):
    var target: ArcPointer[CType]

    def __init__(out self, var target: ArcPointer[CType]):
        self.target = target^


struct MojoSizeOfExpr(Copyable, Equatable, Movable):
    var target: ArcPointer[MojoType]

    def __init__(out self, var target: ArcPointer[MojoType]):
        self.target = target^


struct CCallExpr(Copyable, Equatable, Movable):
    var callee: ArcPointer[CConstExpr]
    var args: List[ArcPointer[CConstExpr]]

    def __init__(
        out self,
        var callee: ArcPointer[CConstExpr],
        var args: List[ArcPointer[CConstExpr]] = List[ArcPointer[CConstExpr]](),
    ):
        self.callee = callee^
        self.args = args^


struct MojoCallExpr(Copyable, Equatable, Movable):
    var callee: ArcPointer[MojoConstExpr]
    var args: List[ArcPointer[MojoConstExpr]]

    def __init__(
        out self,
        var callee: ArcPointer[MojoConstExpr],
        var args: List[ArcPointer[MojoConstExpr]] = List[ArcPointer[MojoConstExpr]](),
    ):
        self.callee = callee^
        self.args = args^


struct Enumerant(Copyable, Equatable, Movable):
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


struct Enum(Copyable, Equatable, Movable):
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


struct Typedef(Copyable, Equatable, Movable):
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


struct CParam(Copyable, Equatable, Movable):
    var name: String
    var type: ArcPointer[CType]
    var doc: Optional[DocComment]

    def __init__(
        out self, var name: String, var type: ArcPointer[CType], var doc: Optional[DocComment] = {}
    ):
        self.name = name^
        self.type = type^
        self.doc = doc^


struct MojoParam(Copyable, Equatable, Movable):
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


struct Function(Copyable, Equatable, Movable):
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


struct Const(Copyable, Equatable, Movable):
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


struct MacroDecl(Copyable, Equatable, Movable):
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


struct GlobalVar(Copyable, Equatable, Movable):
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


struct IRDiagnostic(Copyable, Equatable, Movable):
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


struct TargetABI(Copyable, Equatable, Movable):
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


struct Unit(Copyable, Equatable, Movable):
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


struct PrimitiveDType(Copyable, Equatable, Movable):
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


struct MappingNote(Copyable, Equatable, Movable):
    var severity: MappingSeverity
    var message: String
    var category: String

    def __init__(
        out self, var severity: MappingSeverity, var message: String, var category: String
    ):
        self.severity = severity^
        self.message = message^
        self.category = category^


struct ModuleImport(Copyable, Equatable, Movable):
    var module: String
    var names: List[String]

    def __init__(out self, var module: String, var names: List[String]):
        self.module = module^
        self.names = names^


struct SupportDecl(Copyable, Equatable, Movable):
    var kind: SupportDeclKind

    def __init__(out self, var kind: SupportDeclKind):
        self.kind = kind^


struct ModuleDependencies(Copyable, Equatable, Movable):
    var imports: List[ModuleImport]
    var support_decls: List[SupportDecl]

    def __init__(
        out self,
        var imports: List[ModuleImport] = List[ModuleImport](),
        var support_decls: List[SupportDecl] = List[SupportDecl](),
    ):
        self.imports = imports^
        self.support_decls = support_decls^


struct BuiltinType(Copyable, Equatable, Movable):
    var name: MojoBuiltin

    def __init__(out self, var name: MojoBuiltin):
        self.name = name^


struct NamedType(Copyable, Equatable, Movable):
    var name: String

    def __init__(out self, var name: String):
        self.name = name^


struct DTypeArg(Copyable, Equatable, Movable):
    var value: String

    def __init__(out self, var value: String):
        self.value = value^


struct ConstArg(Copyable, Equatable, Movable):
    var value: IntegerValue

    def __init__(out self, var value: IntegerValue):
        self.value = value^


struct NameArg(Copyable, Equatable, Movable):
    var value: String

    def __init__(out self, var value: String):
        self.value = value^


struct TypeArg(Copyable, Equatable, Movable):
    var type: ArcPointer[MojoType]

    def __init__(out self, var type: ArcPointer[MojoType]):
        self.type = type^


struct ParametricType(Copyable, Equatable, Movable):
    var base: ParametricBase
    var args: List[ParametricArg]

    def __init__(
        out self, var base: ParametricBase, var args: List[ParametricArg] = List[ParametricArg]()
    ):
        self.base = base^
        self.args = args^


struct StoredMember(Copyable, Equatable, Movable):
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


struct PaddingMember(Copyable, Equatable, Movable):
    var name: String
    var size_bytes: Int
    var byte_offset: Int

    def __init__(out self, var name: String, var size_bytes: Int, var byte_offset: Int):
        self.name = name^
        self.size_bytes = size_bytes
        self.byte_offset = byte_offset


struct OpaqueStorageMember(Copyable, Equatable, Movable):
    var name: String
    var size_bytes: Int

    def __init__(out self, var name: String, var size_bytes: Int):
        self.name = name^
        self.size_bytes = size_bytes


struct BitfieldField(Copyable, Equatable, Movable):
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


struct BitfieldGroupMember(Copyable, Equatable, Movable):
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


struct ComptimeMember(Copyable, Equatable, Movable):
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


struct InitializerParam(Copyable, Equatable, Movable):
    var name: String
    var type: ArcPointer[MojoType]

    def __init__(out self, var name: String, var type: ArcPointer[MojoType]):
        self.name = name^
        self.type = type^


struct Initializer(Copyable, Equatable, Movable):
    var params: List[InitializerParam]

    def __init__(out self, var params: List[InitializerParam] = List[InitializerParam]()):
        self.params = params^


struct FlexibleTail(Copyable, Equatable, Movable):
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


struct StructDecl(Copyable, Equatable, Movable):
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


struct AliasDecl(Copyable, Equatable, Movable):
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


struct CallTarget(Copyable, Equatable, Movable):
    var link_mode: LinkMode
    var symbol: String

    def __init__(out self, var link_mode: LinkMode, var symbol: String):
        self.link_mode = link_mode^
        self.symbol = symbol^


struct FunctionDecl(Copyable, Equatable, Movable):
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


struct GlobalDecl(Copyable, Equatable, Movable):
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


struct MojoModule(Copyable, Equatable, Movable):
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


__enum CType(Copyable, Equatable, Movable):
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

    def __eq__(self, other: Self) -> Bool:
        match self:
            case .void_type(a):
                if case .void_type(b) = other:
                    return a == b
                return False
            case .int_type(a):
                if case .int_type(b) = other:
                    return a == b
                return False
            case .float_type(a):
                if case .float_type(b) = other:
                    return a == b
                return False
            case .qualified_type(a):
                if case .qualified_type(b) = other:
                    return a == b
                return False
            case .atomic_type(a):
                if case .atomic_type(b) = other:
                    return a == b
                return False
            case .c_pointer(a):
                if case .c_pointer(b) = other:
                    return a == b
                return False
            case .c_array(a):
                if case .c_array(b) = other:
                    return a == b
                return False
            case .c_function_ptr(a):
                if case .c_function_ptr(b) = other:
                    return a == b
                return False
            case .opaque_record_ref(a):
                if case .opaque_record_ref(b) = other:
                    return a == b
                return False
            case .unsupported_type(a):
                if case .unsupported_type(b) = other:
                    return a == b
                return False
            case .complex_type(a):
                if case .complex_type(b) = other:
                    return a == b
                return False
            case .vector_type(a):
                if case .vector_type(b) = other:
                    return a == b
                return False
            case .struct_ref(a):
                if case .struct_ref(b) = other:
                    return a == b
                return False
            case .enum_ref(a):
                if case .enum_ref(b) = other:
                    return a == b
                return False
            case .type_ref(a):
                if case .type_ref(b) = other:
                    return a == b
                return False


__enum MojoType(Copyable, Equatable, Movable):
    case builtin_type(BuiltinType)
    case named_type(NamedType)
    case mojo_pointer(MojoPointer)
    case mojo_array(MojoArray)
    case mojo_function_ptr(MojoFunctionPtr)
    case parametric_type(ParametricType)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass

    def __eq__(self, other: Self) -> Bool:
        match self:
            case .builtin_type(a):
                if case .builtin_type(b) = other:
                    return a == b
                return False
            case .named_type(a):
                if case .named_type(b) = other:
                    return a == b
                return False
            case .mojo_pointer(a):
                if case .mojo_pointer(b) = other:
                    return a == b
                return False
            case .mojo_array(a):
                if case .mojo_array(b) = other:
                    return a == b
                return False
            case .mojo_function_ptr(a):
                if case .mojo_function_ptr(b) = other:
                    return a == b
                return False
            case .parametric_type(a):
                if case .parametric_type(b) = other:
                    return a == b
                return False


__enum ParametricArg(Copyable, Equatable, Movable):
    case d_type_arg(DTypeArg)
    case const_arg(ConstArg)
    case name_arg(NameArg)
    case type_arg(TypeArg)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass

    def __eq__(self, other: Self) -> Bool:
        match self:
            case .d_type_arg(a):
                if case .d_type_arg(b) = other:
                    return a == b
                return False
            case .const_arg(a):
                if case .const_arg(b) = other:
                    return a == b
                return False
            case .name_arg(a):
                if case .name_arg(b) = other:
                    return a == b
                return False
            case .type_arg(a):
                if case .type_arg(b) = other:
                    return a == b
                return False


__enum CConstExpr(Copyable, Equatable, Movable):
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

    def __eq__(self, other: Self) -> Bool:
        match self:
            case .int_literal(a):
                if case .int_literal(b) = other:
                    return a == b
                return False
            case .c_float_literal(a):
                if case .c_float_literal(b) = other:
                    return a == b
                return False
            case .string_literal(a):
                if case .string_literal(b) = other:
                    return a == b
                return False
            case .char_literal(a):
                if case .char_literal(b) = other:
                    return a == b
                return False
            case .c_null_ptr_literal(a):
                if case .c_null_ptr_literal(b) = other:
                    return a == b
                return False
            case .c_ref_expr(a):
                if case .c_ref_expr(b) = other:
                    return a == b
                return False
            case .c_unary_expr(a):
                if case .c_unary_expr(b) = other:
                    return a == b
                return False
            case .c_binary_expr(a):
                if case .c_binary_expr(b) = other:
                    return a == b
                return False
            case .c_cast_expr(a):
                if case .c_cast_expr(b) = other:
                    return a == b
                return False
            case .c_size_of_expr(a):
                if case .c_size_of_expr(b) = other:
                    return a == b
                return False
            case .c_call_expr(a):
                if case .c_call_expr(b) = other:
                    return a == b
                return False


__enum MojoConstExpr(Copyable, Equatable, Movable):
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

    def __eq__(self, other: Self) -> Bool:
        match self:
            case .int_literal(a):
                if case .int_literal(b) = other:
                    return a == b
                return False
            case .mojo_float_literal(a):
                if case .mojo_float_literal(b) = other:
                    return a == b
                return False
            case .string_literal(a):
                if case .string_literal(b) = other:
                    return a == b
                return False
            case .char_literal(a):
                if case .char_literal(b) = other:
                    return a == b
                return False
            case .mojo_ref_expr(a):
                if case .mojo_ref_expr(b) = other:
                    return a == b
                return False
            case .mojo_unary_expr(a):
                if case .mojo_unary_expr(b) = other:
                    return a == b
                return False
            case .mojo_binary_expr(a):
                if case .mojo_binary_expr(b) = other:
                    return a == b
                return False
            case .mojo_cast_expr(a):
                if case .mojo_cast_expr(b) = other:
                    return a == b
                return False
            case .mojo_size_of_expr(a):
                if case .mojo_size_of_expr(b) = other:
                    return a == b
                return False
            case .mojo_call_expr(a):
                if case .mojo_call_expr(b) = other:
                    return a == b
                return False


__enum Decl(Copyable, Equatable, Movable):
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

    def __eq__(self, other: Self) -> Bool:
        match self:
            case .function(a):
                if case .function(b) = other:
                    return a == b
                return False
            case .struct_decl(a):
                if case .struct_decl(b) = other:
                    return a == b
                return False
            case .enum_decl(a):
                if case .enum_decl(b) = other:
                    return a == b
                return False
            case .typedef(a):
                if case .typedef(b) = other:
                    return a == b
                return False
            case .const_decl(a):
                if case .const_decl(b) = other:
                    return a == b
                return False
            case .macro_decl(a):
                if case .macro_decl(b) = other:
                    return a == b
                return False
            case .global_var(a):
                if case .global_var(b) = other:
                    return a == b
                return False


__enum MojoDecl(Copyable, Equatable, Movable):
    case struct_decl(StructDecl)
    case alias_decl(AliasDecl)
    case function_decl(FunctionDecl)
    case global_decl(GlobalDecl)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass

    def __eq__(self, other: Self) -> Bool:
        match self:
            case .struct_decl(a):
                if case .struct_decl(b) = other:
                    return a == b
                return False
            case .alias_decl(a):
                if case .alias_decl(b) = other:
                    return a == b
                return False
            case .function_decl(a):
                if case .function_decl(b) = other:
                    return a == b
                return False
            case .global_decl(a):
                if case .global_decl(b) = other:
                    return a == b
                return False


__enum StructMember(Copyable, Equatable, Movable):
    case stored_member(StoredMember)
    case padding_member(PaddingMember)
    case opaque_storage_member(OpaqueStorageMember)
    case bitfield_group_member(BitfieldGroupMember)

    def __deinit__(deinit self):
        # Resolve recursive lifecycle inference on the pinned compiler.
        pass

    def __eq__(self, other: Self) -> Bool:
        match self:
            case .stored_member(a):
                if case .stored_member(b) = other:
                    return a == b
                return False
            case .padding_member(a):
                if case .padding_member(b) = other:
                    return a == b
                return False
            case .opaque_storage_member(a):
                if case .opaque_storage_member(b) = other:
                    return a == b
                return False
            case .bitfield_group_member(a):
                if case .bitfield_group_member(b) = other:
                    return a == b
                return False


def equal[T: Equatable](a: T, b: T) -> Bool:
    return a == b

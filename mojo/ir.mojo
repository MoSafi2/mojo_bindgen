# ─────────────────────────────────────────────────────────────────────────────
# mojo_bindgen IR (intermediate representation) — Mojo port.
#
# This module ports the Python `mojo_bindgen/ir.py` IR schema to Mojo. JSON
# serialization/deserialization is an OPTIONAL DEBUG FEATURE, isolated in
# `mojo/serde.mojo` (the only Mojo module that imports EmberJson's `serialize`/
# `deserialize`/`parse`). This module imports just `Value`/`Object` from
# EmberJson, used purely as the storage representation for recursive IR union
# fields — no SerDe logic lives here.
#
# Design notes:
#   * discriminated unions (Type / ConstExpr / Decl / MojoDecl / ParametricArg /
#     StructMember) are represented at the storage level by EmberJson's
#     `Value`. Each concrete variant is a `@fieldwise_init` struct carrying a
#     `kind: String` discriminator (its class name) so JSON round-trips (via
#     `mojo/serde.mojo`) match the Python IR wire format.
#   * enum-like discriminants (IntKind, FloatKind, ...) are modeled as
#     `comptime` String constants grouped inside small structs, so they
#     serialize as bare JSON strings exactly like Python's StrEnum.
# ─────────────────────────────────────────────────────────────────────────────

from emberjson import Value, Object, JsonSerializable, JsonDeserializable, Serializer, Parser, ParseOptions
from emberjson.utils import write_escaped_string

# ============================================================================
# Enum-like discriminants (Python StrEnum → comptime String constants).
# ============================================================================


comptime EnumBase = ImplicitlyCopyable & ImplicitlyDestructible & Hashable & Equatable & Writable

@fieldwise_init
struct IntKind(EnumBase):
    var value: String
    comptime BOOL = IntKind("BOOL")
    comptime CHAR_S = IntKind("CHAR_S")
    comptime CHAR_U = IntKind("CHAR_U")
    comptime SCHAR = IntKind("SCHAR")
    comptime UCHAR = IntKind("UCHAR")
    comptime SHORT = IntKind("SHORT")
    comptime USHORT = IntKind("USHORT")
    comptime INT = IntKind("INT")
    comptime UINT = IntKind("UINT")
    comptime LONG = IntKind("LONG")
    comptime ULONG = IntKind("ULONG")
    comptime LONGLONG = IntKind("LONGLONG")
    comptime ULONGLONG = IntKind("ULONGLONG")
    comptime INT128 = IntKind("INT128")
    comptime UINT128 = IntKind("UINT128")
    comptime WCHAR = IntKind("WCHAR")
    comptime CHAR16 = IntKind("CHAR16")
    comptime CHAR32 = IntKind("CHAR32")
    comptime EXT_INT = IntKind("EXT_INT")

@fieldwise_init
struct FloatKind(EnumBase):
    var value: String
    comptime FLOAT16 = FloatKind("FLOAT16")
    comptime FLOAT = FloatKind("FLOAT")
    comptime DOUBLE = FloatKind("DOUBLE")
    comptime LONG_DOUBLE = FloatKind("LONG_DOUBLE")
    comptime FLOAT128 = FloatKind("FLOAT128")

@fieldwise_init
struct UnsupportedTypeCategory(EnumBase):
    var value: String
    comptime UNEXPOSED = "unexposed"
    comptime VECTOR = "vector"
    comptime COMPLEX = "complex"
    comptime BLOCK = "block"
    comptime OBJC = "objc"
    comptime UNSUPPORTED_EXTENSION = "unsupported_extension"
    comptime INVALID = "invalid"
    comptime UNKNOWN = "unknown"

@fieldwise_init
struct ArrayKind(EnumBase):
    var value: String
    comptime FIXED = "fixed"
    comptime INCOMPLETE = "incomplete"
    comptime FLEXIBLE = "flexible"
    comptime VARIABLE = "variable"

@fieldwise_init
struct FamPattern(EnumBase):
    comptime C99_EMPTY = "c99_empty"
    comptime GNU_ZERO = "gnu_zero"

@fieldwise_init
struct MacroDeclKind(EnumBase):
    var value: String
    comptime OBJECT_LIKE_SUPPORTED = "object_like_supported"
    comptime OBJECT_LIKE_UNSUPPORTED = "object_like_unsupported"
    comptime FUNCTION_LIKE_UNSUPPORTED = "function_like_unsupported"
    comptime EMPTY = "empty"
    comptime PREDEFINED = "predefined"
    comptime INVALID = "invalid"

@fieldwise_init
struct PointerMutability(EnumBase):
    var value: String
    comptime MUT = "mut"
    comptime IMMUT = "immut"

@fieldwise_init
struct PointerOrigin(EnumBase):
    var value: String
    comptime EXTERNAL = "external"
    comptime ANY = "any"

@fieldwise_init
struct ByteOrder(EnumBase):
    var value: String
    comptime LITTLE = "little"
    comptime BIG = "big"

@fieldwise_init
struct MojoBuiltin(EnumBase):
    var value: String
    comptime NONE = "NoneType"
    comptime BOOL = "Bool"
    comptime UINT8 = "UInt8"
    comptime INT128 = "Int128"
    comptime UINT128 = "UInt128"
    comptime FLOAT16 = "Float16"
    comptime C_CHAR = "c_char"
    comptime C_UCHAR = "c_uchar"
    comptime C_SHORT = "c_short"
    comptime C_USHORT = "c_ushort"
    comptime C_INT = "c_int"
    comptime C_UINT = "c_uint"
    comptime C_LONG = "c_long"
    comptime C_ULONG = "c_ulong"
    comptime C_LONG_LONG = "c_long_long"
    comptime C_ULONG_LONG = "c_ulong_long"
    comptime C_FLOAT = "c_float"
    comptime C_DOUBLE = "c_double"
    comptime UNSUPPORTED = "unsupported"

@fieldwise_init
struct StructTraits(EnumBase):
    var value: String
    comptime COPYABLE = "Copyable"
    comptime IMPLICITLY_COPYABLE = "ImplicitlyCopyable"
    comptime MOVABLE = "Movable"
    comptime REGISTER_PASSABLE = "RegisterPassable"
    comptime TRIVIAL_REGISTER_PASSABLE = "TrivialRegisterPassable"

@fieldwise_init
struct StructKind(EnumBase):
    comptime PLAIN = "plain"
    comptime OPAQUE = "opaque"

@fieldwise_init
struct MojoPassability(EnumBase):
    var value: String
    comptime MEMORY_ONLY = "memory_only"
    comptime REGISTER_PASSABLE = "register_passable"
    comptime TRIVIAL_REGISTER_PASSABLE = "trivial_register_passable"

@fieldwise_init
struct AliasKind(EnumBase):
    var value: String
    comptime TYPE_ALIAS = "type_alias"
    comptime CALLBACK_SIGNATURE = "callback_signature"
    comptime UNION_LAYOUT = "union_layout"
    comptime CONST_VALUE = "const_value"
    comptime MACRO_VALUE = "macro_value"

@fieldwise_init
struct FunctionKind(EnumBase):
    var value: String
    comptime WRAPPER = "wrapper"
    comptime VARIADIC_STUB = "variadic_stub"
    comptime NON_REGISTER_RETURN_STUB = "non_register_return_stub"

@fieldwise_init
struct GlobalKind(EnumBase):
    var value: String
    comptime WRAPPER = "wrapper"
    comptime STUB = "stub"

@fieldwise_init
struct LinkMode(EnumBase):
    var value: String
    comptime EXTERNAL_CALL = "external_call"
    comptime OWNED_DL_HANDLE = "owned_dl_handle"

@fieldwise_init
struct MappingSeverity(EnumBase):
    var value: String
    comptime NOTE = "note"
    comptime WARNING = "warning"
    comptime ERROR = "error"

@fieldwise_init
struct ParametricBase(EnumBase):
    var value: String
    comptime SIMD = "SIMD"
    comptime COMPLEX_SIMD = "ComplexSIMD"
    comptime ATOMIC = "Atomic"
    comptime UNSAFE_UNION = "UnsafeUnion"

@fieldwise_init
struct SupportDeclKind(EnumBase):
    var value: String
    comptime DL_HANDLE_HELPERS = "dl_handle_helpers"
    comptime GLOBAL_SYMBOL_HELPERS = "global_symbol_helpers"


@fieldwise_init
struct NodeKind(EnumBase, Defaultable, ImplicitlyCopyable, JsonSerializable, JsonDeserializable):
    """Discriminator for IR node structs (replaces Python's `KIND: ClassVar[str]`).

    String-backed so EmberJson reflection serializes it as a bare JSON string
    matching the Python IR wire format (e.g. `{"kind": "VoidType", ...}`).
    Conforms to `EnumBase` like the other enum-like structs (`IntKind`, ...).
    `Defaultable` + `ImplicitlyCopyable` are needed for EmberJson reflection and
    comptime constant materialization. `JsonSerializable`/`JsonDeserializable`
    are implemented so EmberJson treats `NodeKind` as a bare JSON string (not
    a `{"value": "..."}` object), preserving the Python wire format.
    """

    var value: String

    def __init__(out self):
        self.value = ""

    def name(self) -> String:
        return self.value

    def write_json(self, mut writer: Some[Serializer]):
        write_escaped_string(self.value, writer)

    @staticmethod
    def from_json[
        origin: ImmutOrigin, options: ParseOptions, //
    ](mut p: Parser[origin, options], out s: NodeKind) raises:
        s = NodeKind(p.read_string())

    comptime DOC_COMMENT = NodeKind("DocComment")
    comptime TARGET_ABI = NodeKind("TargetABI")
    comptime MAPPING_NOTE = NodeKind("MappingNote")
    comptime MODULE_IMPORT = NodeKind("ModuleImport")
    comptime SUPPORT_DECL = NodeKind("SupportDecl")
    comptime MODULE_DEPENDENCIES = NodeKind("ModuleDependencies")
    comptime PRIMITIVE_DTYPE = NodeKind("PrimitiveDType")

    comptime VOID_TYPE = NodeKind("VoidType")
    comptime INT_TYPE = NodeKind("IntType")
    comptime FLOAT_TYPE = NodeKind("FloatType")
    comptime QUALIFIED_TYPE = NodeKind("QualifiedType")
    comptime ATOMIC_TYPE = NodeKind("AtomicType")
    comptime POINTER = NodeKind("Pointer")
    comptime ARRAY = NodeKind("Array")
    comptime FUNCTION_PTR = NodeKind("FunctionPtr")
    comptime OPAQUE_RECORD_REF = NodeKind("OpaqueRecordRef")
    comptime UNSUPPORTED_TYPE = NodeKind("UnsupportedType")
    comptime COMPLEX_TYPE = NodeKind("ComplexType")
    comptime VECTOR_TYPE = NodeKind("VectorType")
    comptime STRUCT_REF = NodeKind("StructRef")
    comptime ENUM_REF = NodeKind("EnumRef")
    comptime TYPE_REF = NodeKind("TypeRef")

    comptime INT_LITERAL = NodeKind("IntLiteral")
    comptime FLOAT_LITERAL = NodeKind("FloatLiteral")
    comptime IR_STRING = NodeKind("IRString")
    comptime CHAR_LITERAL = NodeKind("CharLiteral")
    comptime NULL_PTR_LITERAL = NodeKind("NullPtrLiteral")
    comptime REF_EXPR = NodeKind("RefExpr")
    comptime UNARY_EXPR = NodeKind("UnaryExpr")
    comptime BINARY_EXPR = NodeKind("BinaryExpr")
    comptime CAST_EXPR = NodeKind("CastExpr")
    comptime SIZE_OF_EXPR = NodeKind("SizeOfExpr")
    comptime CALL_EXPR = NodeKind("CallExpr")

    comptime FIELD = NodeKind("Field")
    comptime STRUCT = NodeKind("Struct")
    comptime ENUM = NodeKind("Enum")
    comptime TYPEDEF = NodeKind("Typedef")
    comptime FUNCTION = NodeKind("Function")
    comptime CONST = NodeKind("Const")
    comptime MACRO_DECL = NodeKind("MacroDecl")
    comptime GLOBAL_VAR = NodeKind("GlobalVar")
    comptime UNIT = NodeKind("Unit")

    comptime BUILTIN_TYPE = NodeKind("BuiltinType")
    comptime NAMED_TYPE = NodeKind("NamedType")
    comptime DTYPE_ARG = NodeKind("DTypeArg")
    comptime CONST_ARG = NodeKind("ConstArg")
    comptime NAME_ARG = NodeKind("NameArg")
    comptime TYPE_ARG = NodeKind("TypeArg")
    comptime PARAMETRIC_TYPE = NodeKind("ParametricType")

    comptime STORED_MEMBER = NodeKind("StoredMember")
    comptime PADDING_MEMBER = NodeKind("PaddingMember")
    comptime OPAQUE_STORAGE_MEMBER = NodeKind("OpaqueStorageMember")
    comptime BITFIELD_FIELD = NodeKind("BitfieldField")
    comptime BITFIELD_GROUP_MEMBER = NodeKind("BitfieldGroupMember")
    comptime COMPTIME_MEMBER = NodeKind("ComptimeMember")
    comptime INITIALIZER_PARAM = NodeKind("InitializerParam")
    comptime INITIALIZER = NodeKind("Initializer")
    comptime FLEXIBLE_TAIL = NodeKind("FlexibleTail")

    comptime STRUCT_DECL = NodeKind("StructDecl")
    comptime ALIAS_DECL = NodeKind("AliasDecl")
    comptime CALL_TARGET = NodeKind("CallTarget")
    comptime FUNCTION_DECL = NodeKind("FunctionDecl")
    comptime GLOBAL_DECL = NodeKind("GlobalDecl")
    comptime MOJO_MODULE = NodeKind("MojoModule")

    @staticmethod
    def from_name(s: String) raises -> NodeKind:
        if s == "DocComment":
            return NodeKind.DOC_COMMENT
        if s == "TargetABI":
            return NodeKind.TARGET_ABI
        if s == "MappingNote":
            return NodeKind.MAPPING_NOTE
        if s == "ModuleImport":
            return NodeKind.MODULE_IMPORT
        if s == "SupportDecl":
            return NodeKind.SUPPORT_DECL
        if s == "ModuleDependencies":
            return NodeKind.MODULE_DEPENDENCIES
        if s == "PrimitiveDType":
            return NodeKind.PRIMITIVE_DTYPE
        if s == "VoidType":
            return NodeKind.VOID_TYPE
        if s == "IntType":
            return NodeKind.INT_TYPE
        if s == "FloatType":
            return NodeKind.FLOAT_TYPE
        if s == "QualifiedType":
            return NodeKind.QUALIFIED_TYPE
        if s == "AtomicType":
            return NodeKind.ATOMIC_TYPE
        if s == "Pointer":
            return NodeKind.POINTER
        if s == "Array":
            return NodeKind.ARRAY
        if s == "FunctionPtr":
            return NodeKind.FUNCTION_PTR
        if s == "OpaqueRecordRef":
            return NodeKind.OPAQUE_RECORD_REF
        if s == "UnsupportedType":
            return NodeKind.UNSUPPORTED_TYPE
        if s == "ComplexType":
            return NodeKind.COMPLEX_TYPE
        if s == "VectorType":
            return NodeKind.VECTOR_TYPE
        if s == "StructRef":
            return NodeKind.STRUCT_REF
        if s == "EnumRef":
            return NodeKind.ENUM_REF
        if s == "TypeRef":
            return NodeKind.TYPE_REF
        if s == "IntLiteral":
            return NodeKind.INT_LITERAL
        if s == "FloatLiteral":
            return NodeKind.FLOAT_LITERAL
        if s == "IRString":
            return NodeKind.IR_STRING
        if s == "CharLiteral":
            return NodeKind.CHAR_LITERAL
        if s == "NullPtrLiteral":
            return NodeKind.NULL_PTR_LITERAL
        if s == "RefExpr":
            return NodeKind.REF_EXPR
        if s == "UnaryExpr":
            return NodeKind.UNARY_EXPR
        if s == "BinaryExpr":
            return NodeKind.BINARY_EXPR
        if s == "CastExpr":
            return NodeKind.CAST_EXPR
        if s == "SizeOfExpr":
            return NodeKind.SIZE_OF_EXPR
        if s == "CallExpr":
            return NodeKind.CALL_EXPR
        if s == "Field":
            return NodeKind.FIELD
        if s == "Struct":
            return NodeKind.STRUCT
        if s == "Enum":
            return NodeKind.ENUM
        if s == "Typedef":
            return NodeKind.TYPEDEF
        if s == "Function":
            return NodeKind.FUNCTION
        if s == "Const":
            return NodeKind.CONST
        if s == "MacroDecl":
            return NodeKind.MACRO_DECL
        if s == "GlobalVar":
            return NodeKind.GLOBAL_VAR
        if s == "Unit":
            return NodeKind.UNIT
        if s == "BuiltinType":
            return NodeKind.BUILTIN_TYPE
        if s == "NamedType":
            return NodeKind.NAMED_TYPE
        if s == "DTypeArg":
            return NodeKind.DTYPE_ARG
        if s == "ConstArg":
            return NodeKind.CONST_ARG
        if s == "NameArg":
            return NodeKind.NAME_ARG
        if s == "TypeArg":
            return NodeKind.TYPE_ARG
        if s == "ParametricType":
            return NodeKind.PARAMETRIC_TYPE
        if s == "StoredMember":
            return NodeKind.STORED_MEMBER
        if s == "PaddingMember":
            return NodeKind.PADDING_MEMBER
        if s == "OpaqueStorageMember":
            return NodeKind.OPAQUE_STORAGE_MEMBER
        if s == "BitfieldField":
            return NodeKind.BITFIELD_FIELD
        if s == "BitfieldGroupMember":
            return NodeKind.BITFIELD_GROUP_MEMBER
        if s == "ComptimeMember":
            return NodeKind.COMPTIME_MEMBER
        if s == "InitializerParam":
            return NodeKind.INITIALIZER_PARAM
        if s == "Initializer":
            return NodeKind.INITIALIZER
        if s == "FlexibleTail":
            return NodeKind.FLEXIBLE_TAIL
        if s == "StructDecl":
            return NodeKind.STRUCT_DECL
        if s == "AliasDecl":
            return NodeKind.ALIAS_DECL
        if s == "CallTarget":
            return NodeKind.CALL_TARGET
        if s == "FunctionDecl":
            return NodeKind.FUNCTION_DECL
        if s == "GlobalDecl":
            return NodeKind.GLOBAL_DECL
        if s == "MojoModule":
            return NodeKind.MOJO_MODULE
        raise Error("unknown NodeKind name: " + s)


# ============================================================================
# SerDe helpers.
# ============================================================================

# Concrete IR structs must be Defaultable, Movable and ImplicitlyDestructible
# so that (a) EmberJson can default-construct them before filling fields and
# (b) they can be returned / stored in Lists.
comptime IRBase = Defaultable & Movable & ImplicitlyDestructible & Copyable


# ============================================================================
# TypeNode — marker trait mirroring Python's `Type = Union[...]`.
#
# Mojo has no tagged-union type, so the 18 concrete variants of the C/Mojo
# type tree conform to this trait. Generic functions constrained with
# `[T: TypeNode]` are statically restricted to those variants only — a
# ConstExpr or Decl node will not satisfy the bound (compile error),
# matching the safety of Python's `: Type` annotation.
#
# Storage of recursive type fields stays `Value` (see header notes); the
# trait is for generic-function parameter restriction and polymorphic
# dispatch via `node_kind()`. The `to_value()` lift and `deserialize_*`
# helpers live in `mojo/serde.mojo` (optional debug SerDe).
# ============================================================================
trait TypeNode:
    def node_kind(self) -> NodeKind:
        return NodeKind.VOID_TYPE


# ─────────────────────────────────────────────
# Shared small structs (no `kind` discriminator).
# ─────────────────────────────────────────────

@fieldwise_init
struct Qualifiers(IRBase):
    # NOTE: no `kind` discriminator — Python IR sets KIND=None for Qualifiers.
    var is_const: Bool
    var is_volatile: Bool
    var is_restrict: Bool

    def __init__(out self):
        self.is_const = False
        self.is_volatile = False
        self.is_restrict = False


@fieldwise_init
struct DocComment(IRBase):
    var kind: NodeKind
    var text: String
    var brief: Optional[String]
    var source: String

    def __init__(out self):
        self.kind = NodeKind.DOC_COMMENT
        self.text = ""
        self.brief = None
        self.source = "clang_raw"


struct TargetABI(IRBase):
    var kind: NodeKind
    var pointer_size_bytes: Int
    var pointer_align_bytes: Int
    var byte_order: String

    def __init__(out self):
        self.kind = NodeKind.TARGET_ABI
        self.pointer_size_bytes = 0
        self.pointer_align_bytes = 0
        self.byte_order = ByteOrder.LITTLE


@fieldwise_init
struct IRDiagnostic(IRBase):
    # NOTE: no `kind` discriminator — Python IR sets KIND=None for IRDiagnostic.
    var severity: String
    var message: String
    var file: Optional[String]
    var line: Optional[Int]
    var col: Optional[Int]
    var decl_id: Optional[String]

    def __init__(out self):
        self.severity = ""
        self.message = ""
        self.file = None
        self.line = None
        self.col = None
        self.decl_id = None


@fieldwise_init
struct MappingNote(IRBase):
    var kind: NodeKind
    var severity: String
    var message: String
    var category: String

    def __init__(out self):
        self.kind = NodeKind.MAPPING_NOTE
        self.severity = MappingSeverity.NOTE
        self.message = ""
        self.category = ""


@fieldwise_init
struct ModuleImport(IRBase):
    var kind: NodeKind
    var module: String
    var names: List[String]

    def __init__(out self):
        self.kind = NodeKind.MODULE_IMPORT
        self.module = ""
        self.names = List[String]()


@fieldwise_init
struct SupportDecl(IRBase):
    var kind: NodeKind
    var kind_value: String

    def __init__(out self):
        self.kind = NodeKind.SUPPORT_DECL
        self.kind_value = SupportDeclKind.DL_HANDLE_HELPERS


@fieldwise_init
struct ModuleDependencies(IRBase):
    var kind: NodeKind
    var imports: List[ModuleImport]
    var support_decls: List[SupportDecl]

    def __init__(out self):
        self.kind = NodeKind.MODULE_DEPENDENCIES
        self.imports = List[ModuleImport]()
        self.support_decls = List[SupportDecl]()


@fieldwise_init
struct PrimitiveDType(IRBase):
    var kind: NodeKind
    var kind_field: String
    var signed: Bool
    var dtype: String
    var width_bytes: Int

    def __init__(out self):
        self.kind = NodeKind.PRIMITIVE_DTYPE
        self.kind_field = String(IntKind.INT)
        self.signed = True
        self.dtype = "DType.int32"
        self.width_bytes = 4


# ─────────────────────────────────────────────
# Type — recursive type tree (each variant carries `kind`).
# ─────────────────────────────────────────────

@fieldwise_init
struct VoidType(IRBase, TypeNode):
    var kind: NodeKind

    def __init__(out self):
        self.kind = NodeKind.VOID_TYPE

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct IntType(IRBase, TypeNode):
    var kind: NodeKind
    var int_kind: IntKind
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var ext_bits: Optional[Int]

    def __init__(out self):
        self.kind = NodeKind.INT_TYPE
        self.int_kind = IntKind.INT
        self.size_bytes = 0
        self.align_bytes = None
        self.ext_bits = None

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct FloatType(IRBase, TypeNode):
    var kind: NodeKind
    var float_kind: FloatKind
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = NodeKind.FLOAT_TYPE
        self.float_kind = FloatKind.FLOAT
        self.size_bytes = 0
        self.align_bytes = None

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct QualifiedType(IRBase, TypeNode):
    var kind: NodeKind
    var unqualified: Value
    var qualifiers: Qualifiers

    def __init__(out self):
        self.kind = NodeKind.QUALIFIED_TYPE
        self.unqualified = Value()
        self.qualifiers = Qualifiers()

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct AtomicType(IRBase, TypeNode):
    var kind: NodeKind
    var value_type: Value

    def __init__(out self):
        self.kind = NodeKind.ATOMIC_TYPE
        self.value_type = Value()

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct Pointer(IRBase, TypeNode):
    var kind: NodeKind
    var pointee: Optional[Value]
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var mutability: String
    var origin: String
    var nullable: Bool

    def __init__(out self):
        self.kind = NodeKind.POINTER
        self.pointee = None
        self.size_bytes = 0
        self.align_bytes = None
        self.mutability = PointerMutability.MUT
        self.origin = PointerOrigin.EXTERNAL
        self.nullable = False

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct Array(IRBase, TypeNode):
    var kind: NodeKind
    var element: Value
    var size: Optional[Int]
    var array_kind: String
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = NodeKind.ARRAY
        self.element = Value()
        self.size = None
        self.array_kind = ArrayKind.FIXED
        self.size_bytes = 0
        self.align_bytes = None

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct FunctionPtr(IRBase, TypeNode):
    var kind: NodeKind
    var ret: Value
    var params: List[Param]
    var param_names: Optional[List[String]]
    var is_variadic: Bool
    var calling_convention: Optional[String]
    var is_noreturn: Bool
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var abi: String
    var thin: Bool
    var raises: Bool

    def __init__(out self):
        self.kind = NodeKind.FUNCTION_PTR
        self.ret = Value()
        self.params = List[Param]()
        self.param_names = None
        self.is_variadic = False
        self.calling_convention = None
        self.is_noreturn = False
        self.size_bytes = 0
        self.align_bytes = None
        self.abi = "C"
        self.thin = True
        self.raises = False

    def node_kind(self) -> NodeKind:
        return self.kind

# Forward declaration trick: `Param` is defined below the Decl section but is
# referenced by `FunctionPtr`. Mojo resolves structs at module scope, so the
# full definition appearing later in the same file is fine.


@fieldwise_init
struct OpaqueRecordRef(IRBase, TypeNode):
    var kind: NodeKind
    var decl_id: String
    var name: String
    var c_name: String
    var is_union: Bool
    var size_bytes: Optional[Int]
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = NodeKind.OPAQUE_RECORD_REF
        self.decl_id = ""
        self.name = ""
        self.c_name = ""
        self.is_union = False
        self.size_bytes = None
        self.align_bytes = None

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct UnsupportedType(IRBase, TypeNode):
    var kind: NodeKind
    var category: String
    var spelling: String
    var reason: String
    var size_bytes: Optional[Int]
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = NodeKind.UNSUPPORTED_TYPE
        self.category = UnsupportedTypeCategory.UNKNOWN
        self.spelling = ""
        self.reason = ""
        self.size_bytes = None
        self.align_bytes = None

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct ComplexType(IRBase, TypeNode):
    var kind: NodeKind
    var element: FloatType
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = NodeKind.COMPLEX_TYPE
        self.element = FloatType()
        self.size_bytes = 0
        self.align_bytes = None

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct VectorType(IRBase, TypeNode):
    var kind: NodeKind
    var element: Value
    var count: Optional[Int]
    var size_bytes: Int
    var is_ext_vector: Bool
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = NodeKind.VECTOR_TYPE
        self.element = Value()
        self.count = None
        self.size_bytes = 0
        self.is_ext_vector = False
        self.align_bytes = None

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct StructRef(IRBase, TypeNode):
    var kind: NodeKind
    var decl_id: String
    var name: String
    var c_name: String
    var is_union: Bool
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var is_anonymous: Bool

    def __init__(out self):
        self.kind = NodeKind.STRUCT_REF
        self.decl_id = ""
        self.name = ""
        self.c_name = ""
        self.is_union = False
        self.size_bytes = 0
        self.align_bytes = None
        self.is_anonymous = False

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct EnumRef(IRBase, TypeNode):
    var kind: NodeKind
    var decl_id: String
    var name: String
    var c_name: String
    var underlying: IntType

    def __init__(out self):
        self.kind = NodeKind.ENUM_REF
        self.decl_id = ""
        self.name = ""
        self.c_name = ""
        self.underlying = IntType()

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct TypeRef(IRBase, TypeNode):
    var kind: NodeKind
    var decl_id: String
    var name: String
    var canonical: Value

    def __init__(out self):
        self.kind = NodeKind.TYPE_REF
        self.decl_id = ""
        self.name = ""
        self.canonical = Value()

    def node_kind(self) -> NodeKind:
        return self.kind

# ─────────────────────────────────────────────
# ConstExpr — structured constant-expression subset.
# ─────────────────────────────────────────────

@fieldwise_init
struct IntLiteral(IRBase):
    var kind: NodeKind
    var value: Int

    def __init__(out self):
        self.kind = NodeKind.INT_LITERAL
        self.value = 0


@fieldwise_init
struct FloatLiteral(IRBase):
    var kind: NodeKind
    var value: Value

    def __init__(out self):
        self.kind = NodeKind.FLOAT_LITERAL
        self.value = Value()


@fieldwise_init
struct IRString(IRBase):
    var kind: NodeKind
    var value: String

    def __init__(out self):
        self.kind = NodeKind.IR_STRING
        self.value = ""


@fieldwise_init
struct CharLiteral(IRBase):
    var kind: NodeKind
    var value: String

    def __init__(out self):
        self.kind = NodeKind.CHAR_LITERAL
        self.value = ""


@fieldwise_init
struct NullPtrLiteral(IRBase):
    var kind: NodeKind

    def __init__(out self):
        self.kind = NodeKind.NULL_PTR_LITERAL


@fieldwise_init
struct RefExpr(IRBase):
    var kind: NodeKind
    var name: String

    def __init__(out self):
        self.kind = NodeKind.REF_EXPR
        self.name = ""


@fieldwise_init
struct UnaryExpr(IRBase):
    var kind: NodeKind
    var op: String
    var operand: Value

    def __init__(out self):
        self.kind = NodeKind.UNARY_EXPR
        self.op = ""
        self.operand = Value()


@fieldwise_init
struct BinaryExpr(IRBase):
    var kind: NodeKind
    var op: String
    var lhs: Value
    var rhs: Value

    def __init__(out self):
        self.kind = NodeKind.BINARY_EXPR
        self.op = ""
        self.lhs = Value()
        self.rhs = Value()


@fieldwise_init
struct CastExpr(IRBase):
    var kind: NodeKind
    var target: Value
    var expr: Value

    def __init__(out self):
        self.kind = NodeKind.CAST_EXPR
        self.target = Value()
        self.expr = Value()


@fieldwise_init
struct SizeOfExpr(IRBase):
    var kind: NodeKind
    var target: Value

    def __init__(out self):
        self.kind = NodeKind.SIZE_OF_EXPR
        self.target = Value()


@fieldwise_init
struct CallExpr(IRBase):
    var kind: NodeKind
    var callee: Value
    var args: List[Value]

    def __init__(out self):
        self.kind = NodeKind.CALL_EXPR
        self.callee = Value()
        self.args = List[Value]()


# ─────────────────────────────────────────────
# Declaration nodes (C-facing).
# ─────────────────────────────────────────────

@fieldwise_init
struct Field(IRBase):
    var kind: NodeKind
    var name: String
    var source_name: String
    var type_field: Value
    var byte_offset: Int
    var size_bytes: Int
    var is_anonymous: Bool
    var is_bitfield: Bool
    var bit_offset: Int
    var bit_width: Int
    var fam_pattern: Optional[String]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.FIELD
        self.name = ""
        self.source_name = ""
        self.type_field = Value()
        self.byte_offset = 0
        self.size_bytes = 0
        self.is_anonymous = False
        self.is_bitfield = False
        self.bit_offset = 0
        self.bit_width = 0
        self.fam_pattern = None
        self.doc = None


@fieldwise_init
struct Enumerant(IRBase):
    # NOTE: no `kind` discriminator — Python IR sets KIND=None for Enumerant.
    var name: String
    var c_name: String
    var value: Int
    var enum_decl_id: Optional[String]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.name = ""
        self.c_name = ""
        self.value = 0
        self.enum_decl_id = None
        self.doc = None


@fieldwise_init
struct Param(IRBase):
    # NOTE: no `kind` discriminator — Python IR sets KIND=None for Param.
    var name: String
    var type_field: Value
    var doc: Optional[DocComment]

    def __init__(out self):
        self.name = ""
        self.type_field = Value()
        self.doc = None


@fieldwise_init
struct Struct(IRBase):
    var kind: NodeKind
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

    def __init__(out self):
        self.kind = NodeKind.STRUCT
        self.decl_id = ""
        self.name = ""
        self.c_name = ""
        self.fields = List[Field]()
        self.size_bytes = 0
        self.align_bytes = 0
        self.is_union = False
        self.is_anonymous = False
        self.is_complete = True
        self.is_packed = False
        self.requested_align_bytes = None
        self.doc = None


@fieldwise_init
struct Enum(IRBase):
    var kind: NodeKind
    var decl_id: String
    var name: String
    var c_name: String
    var underlying: IntType
    var enumerants: List[Enumerant]
    var alias_names: List[String]
    var is_anonymous: Bool
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.ENUM
        self.decl_id = ""
        self.name = ""
        self.c_name = ""
        self.underlying = IntType()
        self.enumerants = List[Enumerant]()
        self.alias_names = List[String]()
        self.is_anonymous = False
        self.doc = None


@fieldwise_init
struct Typedef(IRBase):
    var kind: NodeKind
    var decl_id: String
    var name: String
    var aliased: Value
    var canonical: Value
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.TYPEDEF
        self.decl_id = ""
        self.name = ""
        self.aliased = Value()
        self.canonical = Value()
        self.doc = None


@fieldwise_init
struct Function(IRBase):
    var kind: NodeKind
    var decl_id: String
    var name: String
    var link_name: String
    var ret: Value
    var params: List[Param]
    var is_variadic: Bool
    var calling_convention: Optional[String]
    var is_noreturn: Bool
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.FUNCTION
        self.decl_id = ""
        self.name = ""
        self.link_name = ""
        self.ret = Value()
        self.params = List[Param]()
        self.is_variadic = False
        self.calling_convention = None
        self.is_noreturn = False
        self.doc = None


@fieldwise_init
struct Const(IRBase):
    var kind: NodeKind
    var name: String
    var type_field: Value
    var expr: Value
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.CONST
        self.name = ""
        self.type_field = Value()
        self.expr = Value()
        self.doc = None


@fieldwise_init
struct MacroDecl(IRBase):
    var kind: NodeKind
    var name: String
    var tokens: List[String]
    var macro_kind: String
    var expr: Optional[Value]
    var type_field: Optional[Value]
    var diagnostic: Optional[String]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.MACRO_DECL
        self.name = ""
        self.tokens = List[String]()
        self.macro_kind = MacroDeclKind.INVALID
        self.expr = None
        self.type_field = None
        self.diagnostic = None
        self.doc = None


@fieldwise_init
struct GlobalVar(IRBase):
    var kind: NodeKind
    var decl_id: String
    var name: String
    var link_name: String
    var type_field: Value
    var is_const: Bool
    var initializer: Optional[Value]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.GLOBAL_VAR
        self.decl_id = ""
        self.name = ""
        self.link_name = ""
        self.type_field = Value()
        self.is_const = False
        self.initializer = None
        self.doc = None


@fieldwise_init
struct Unit(IRBase):
    var kind: NodeKind
    var source_header: String
    var library: String
    var link_name: String
    var target_abi: TargetABI
    var decls: List[Value]
    var diagnostics: List[IRDiagnostic]

    def __init__(out self):
        self.kind = NodeKind.UNIT
        self.source_header = ""
        self.library = ""
        self.link_name = ""
        self.target_abi = TargetABI()
        self.decls = List[Value]()
        self.diagnostics = List[IRDiagnostic]()


# ─────────────────────────────────────────────
# Mojo-facing IR nodes.
# ─────────────────────────────────────────────

@fieldwise_init
struct BuiltinType(IRBase, TypeNode):
    var kind: NodeKind
    var name: String

    def __init__(out self):
        self.kind = NodeKind.BUILTIN_TYPE
        self.name = MojoBuiltin.NONE

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct NamedType(IRBase, TypeNode):
    var kind: NodeKind
    var name: String

    def __init__(out self):
        self.kind = NodeKind.NAMED_TYPE
        self.name = ""

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct DTypeArg(IRBase):
    var kind: NodeKind
    var value: String

    def __init__(out self):
        self.kind = NodeKind.DTYPE_ARG
        self.value = ""


@fieldwise_init
struct ConstArg(IRBase):
    var kind: NodeKind
    var value: Int

    def __init__(out self):
        self.kind = NodeKind.CONST_ARG
        self.value = 0


@fieldwise_init
struct NameArg(IRBase):
    var kind: NodeKind
    var value: String

    def __init__(out self):
        self.kind = NodeKind.NAME_ARG
        self.value = ""


@fieldwise_init
struct TypeArg(IRBase):
    var kind: NodeKind
    var type_field: Value

    def __init__(out self):
        self.kind = NodeKind.TYPE_ARG
        self.type_field = Value()


@fieldwise_init
struct ParametricType(IRBase, TypeNode):
    var kind: NodeKind
    var base: String
    var args: List[Value]

    def __init__(out self):
        self.kind = NodeKind.PARAMETRIC_TYPE
        self.base = ParametricBase.SIMD
        self.args = List[Value]()

    def node_kind(self) -> NodeKind:
        return self.kind

@fieldwise_init
struct StoredMember(IRBase):
    var kind: NodeKind
    var index: Int
    var name: String
    var type_field: Value
    var byte_offset: Int
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.STORED_MEMBER
        self.index = 0
        self.name = ""
        self.type_field = Value()
        self.byte_offset = 0
        self.doc = None


@fieldwise_init
struct PaddingMember(IRBase):
    var kind: NodeKind
    var name: String
    var size_bytes: Int
    var byte_offset: Int

    def __init__(out self):
        self.kind = NodeKind.PADDING_MEMBER
        self.name = ""
        self.size_bytes = 0
        self.byte_offset = 0


@fieldwise_init
struct OpaqueStorageMember(IRBase):
    var kind: NodeKind
    var name: String
    var size_bytes: Int

    def __init__(out self):
        self.kind = NodeKind.OPAQUE_STORAGE_MEMBER
        self.name = ""
        self.size_bytes = 0


@fieldwise_init
struct BitfieldField(IRBase):
    var kind: NodeKind
    var index: Int
    var name: String
    var logical_type: Value
    var bit_offset: Int
    var bit_width: Int
    var signed: Bool
    var bool_semantics: Bool
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.BITFIELD_FIELD
        self.index = 0
        self.name = ""
        self.logical_type = Value()
        self.bit_offset = 0
        self.bit_width = 0
        self.signed = False
        self.bool_semantics = False
        self.doc = None


@fieldwise_init
struct BitfieldGroupMember(IRBase):
    var kind: NodeKind
    var storage_name: String
    var storage_type: Value
    var byte_offset: Int
    var first_index: Int
    var storage_width_bits: Int
    var fields: List[BitfieldField]

    def __init__(out self):
        self.kind = NodeKind.BITFIELD_GROUP_MEMBER
        self.storage_name = ""
        self.storage_type = Value()
        self.byte_offset = 0
        self.first_index = 0
        self.storage_width_bits = 0
        self.fields = List[BitfieldField]()


@fieldwise_init
struct ComptimeMember(IRBase):
    var kind: NodeKind
    var name: String
    var type_value: Optional[Value]
    var const_value: Optional[Value]

    def __init__(out self):
        self.kind = NodeKind.COMPTIME_MEMBER
        self.name = ""
        self.type_value = None
        self.const_value = None


@fieldwise_init
struct InitializerParam(IRBase):
    var kind: NodeKind
    var name: String
    var type_field: Value

    def __init__(out self):
        self.kind = NodeKind.INITIALIZER_PARAM
        self.name = ""
        self.type_field = Value()


@fieldwise_init
struct Initializer(IRBase):
    var kind: NodeKind
    var params: List[InitializerParam]

    def __init__(out self):
        self.kind = NodeKind.INITIALIZER
        self.params = List[InitializerParam]()


@fieldwise_init
struct FlexibleTail(IRBase):
    var kind: NodeKind
    var field_name: String
    var element_type: Value
    var pattern: String
    var byte_offset: Int

    def __init__(out self):
        self.kind = NodeKind.FLEXIBLE_TAIL
        self.field_name = ""
        self.element_type = Value()
        self.pattern = ""
        self.byte_offset = 0


@fieldwise_init
struct StructDecl(IRBase):
    var kind: NodeKind
    var struct_kind: String
    var name: String
    var traits: List[String]
    var passability: String
    var align: Optional[Int]
    var align_decorator: Optional[Int]
    var fieldwise_init: Bool
    var members: List[Value]
    var comptime_members: List[ComptimeMember]
    var initializers: List[Initializer]
    var flexible_tail: Optional[FlexibleTail]
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.STRUCT_DECL
        self.struct_kind = StructKind.PLAIN
        self.name = ""
        self.traits = List[String]()
        self.passability = MojoPassability.MEMORY_ONLY
        self.align = None
        self.align_decorator = None
        self.fieldwise_init = False
        self.members = List[Value]()
        self.comptime_members = List[ComptimeMember]()
        self.initializers = List[Initializer]()
        self.flexible_tail = None
        self.diagnostics = List[MappingNote]()
        self.doc = None


@fieldwise_init
struct AliasDecl(IRBase):
    var kind: NodeKind
    var alias_kind: String
    var name: String
    var type_value: Optional[Value]
    var const_type: Optional[Value]
    var const_value: Optional[Value]
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.ALIAS_DECL
        self.alias_kind = AliasKind.TYPE_ALIAS
        self.name = ""
        self.type_value = None
        self.const_type = None
        self.const_value = None
        self.diagnostics = List[MappingNote]()
        self.doc = None

    def has_payload(self) -> Bool:
        return self.type_value is not None or self.const_value is not None

    def has_type_payload(self) -> Bool:
        return self.type_value is not None and self.const_value is None

    def has_const_payload(self) -> Bool:
        return self.const_value is not None and self.type_value is None


@fieldwise_init
struct CallTarget(IRBase):
    var kind: NodeKind
    var link_mode: String
    var symbol: String

    def __init__(out self):
        self.kind = NodeKind.CALL_TARGET
        self.link_mode = LinkMode.EXTERNAL_CALL
        self.symbol = ""


@fieldwise_init
struct FunctionDecl(IRBase):
    var kind: NodeKind
    var function_kind: String
    var name: String
    var link_name: String
    var params: List[Param]
    var return_type: Value
    var call_target: CallTarget
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.FUNCTION_DECL
        self.function_kind = FunctionKind.WRAPPER
        self.name = ""
        self.link_name = ""
        self.params = List[Param]()
        self.return_type = Value()
        self.call_target = CallTarget()
        self.diagnostics = List[MappingNote]()
        self.doc = None


@fieldwise_init
struct GlobalDecl(IRBase):
    var kind: NodeKind
    var global_kind: String
    var name: String
    var link_name: String
    var value_type: Value
    var is_const: Bool
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = NodeKind.GLOBAL_DECL
        self.global_kind = GlobalKind.WRAPPER
        self.name = ""
        self.link_name = ""
        self.value_type = Value()
        self.is_const = False
        self.diagnostics = List[MappingNote]()
        self.doc = None


@fieldwise_init
struct MojoModule(IRBase):
    var kind: NodeKind
    var source_header: String
    var library: String
    var link_name: String
    var link_mode: String
    var library_path_hint: Optional[String]
    var dependencies: ModuleDependencies
    var decls: List[Value]

    def __init__(out self):
        self.kind = NodeKind.MOJO_MODULE
        self.source_header = ""
        self.library = ""
        self.link_name = ""
        self.link_mode = LinkMode.EXTERNAL_CALL
        self.library_path_hint = None
        self.dependencies = ModuleDependencies()
        self.decls = List[Value]()


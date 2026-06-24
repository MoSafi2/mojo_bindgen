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

from emberjson import Value, Object

# ============================================================================
# Type-union aliases.
#
# Recursive C/Mojo IR unions are stored as `Value` to side-step Mojo's
# finite-size struct restriction (a struct cannot directly embed a union that
# contains the struct). Typed accessors can be layered on top later; for now
# `Value` gives faithful JSON round-trips for every variant.
# ============================================================================
comptime ConstExprNode = Value
comptime DeclNode = Value
comptime MojoDeclNode = Value
comptime ParametricArgNode = Value
comptime StructMemberNode = Value


# ============================================================================
# Enum-like discriminants (Python StrEnum → comptime String constants).
# ============================================================================


comptime EnumBase = Copyable & ImplicitlyDestructible & Hashable & Equatable

@fieldwise_init
struct IntKind(EnumBase):
    var value: String
    comptime BOOL = "BOOL"
    comptime CHAR_S = "CHAR_S"
    comptime CHAR_U = "CHAR_U"
    comptime SCHAR = "SCHAR"
    comptime UCHAR = "UCHAR"
    comptime SHORT = "SHORT"
    comptime USHORT = "USHORT"
    comptime INT = "INT"
    comptime UINT = "UINT"
    comptime LONG = "LONG"
    comptime ULONG = "ULONG"
    comptime LONGLONG = "LONGLONG"
    comptime ULONGLONG = "ULONGLONG"
    comptime INT128 = "INT128"
    comptime UINT128 = "UINT128"
    comptime WCHAR = "WCHAR"
    comptime CHAR16 = "CHAR16"
    comptime CHAR32 = "CHAR32"
    comptime EXT_INT = "EXT_INT"

@fieldwise_init
struct FloatKind(EnumBase):
    var value: String
    comptime FLOAT16 = "FLOAT16"
    comptime FLOAT = "FLOAT"
    comptime DOUBLE = "DOUBLE"
    comptime LONG_DOUBLE = "LONG_DOUBLE"
    comptime FLOAT128 = "FLOAT128"

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
    def node_kind(self) -> String:
        return ""


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
    var kind: String
    var text: String
    var brief: Optional[String]
    var source: String

    def __init__(out self):
        self.kind = "DocComment"
        self.text = ""
        self.brief = None
        self.source = "clang_raw"


struct TargetABI(IRBase):
    var kind: String
    var pointer_size_bytes: Int
    var pointer_align_bytes: Int
    var byte_order: String

    def __init__(out self):
        self.kind = "TargetABI"
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
    var kind: String
    var severity: String
    var message: String
    var category: String

    def __init__(out self):
        self.kind = "MappingNote"
        self.severity = MappingSeverity.NOTE
        self.message = ""
        self.category = ""


@fieldwise_init
struct ModuleImport(IRBase):
    var kind: String
    var module: String
    var names: List[String]

    def __init__(out self):
        self.kind = "ModuleImport"
        self.module = ""
        self.names = List[String]()


@fieldwise_init
struct SupportDecl(IRBase):
    var kind: String
    var kind_value: String

    def __init__(out self):
        self.kind = "SupportDecl"
        self.kind_value = SupportDeclKind.DL_HANDLE_HELPERS


@fieldwise_init
struct ModuleDependencies(IRBase):
    var kind: String
    var imports: List[ModuleImport]
    var support_decls: List[SupportDecl]

    def __init__(out self):
        self.kind = "ModuleDependencies"
        self.imports = List[ModuleImport]()
        self.support_decls = List[SupportDecl]()


@fieldwise_init
struct PrimitiveDType(IRBase):
    var kind: String
    var kind_field: String
    var signed: Bool
    var dtype: String
    var width_bytes: Int

    def __init__(out self):
        self.kind = "PrimitiveDType"
        self.kind_field = IntKind.INT
        self.signed = True
        self.dtype = "DType.int32"
        self.width_bytes = 4


# ─────────────────────────────────────────────
# Type — recursive type tree (each variant carries `kind`).
# ─────────────────────────────────────────────

@fieldwise_init
struct VoidType(IRBase, TypeNode):
    var kind: String

    def __init__(out self):
        self.kind = "VoidType"

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct IntType(IRBase, TypeNode):
    var kind: String
    var int_kind: String
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var ext_bits: Optional[Int]

    def __init__(out self):
        self.kind = "IntType"
        self.int_kind = IntKind.INT
        self.size_bytes = 0
        self.align_bytes = None
        self.ext_bits = None

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct FloatType(IRBase, TypeNode):
    var kind: String
    var float_kind: String
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = "FloatType"
        self.float_kind = FloatKind.FLOAT
        self.size_bytes = 0
        self.align_bytes = None

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct QualifiedType(IRBase, TypeNode):
    var kind: String
    var unqualified: Value
    var qualifiers: Qualifiers

    def __init__(out self):
        self.kind = "QualifiedType"
        self.unqualified = Value()
        self.qualifiers = Qualifiers()

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct AtomicType(IRBase, TypeNode):
    var kind: String
    var value_type: Value

    def __init__(out self):
        self.kind = "AtomicType"
        self.value_type = Value()

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct Pointer(IRBase, TypeNode):
    var kind: String
    var pointee: Optional[Value]
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var mutability: String
    var origin: String
    var nullable: Bool

    def __init__(out self):
        self.kind = "Pointer"
        self.pointee = None
        self.size_bytes = 0
        self.align_bytes = None
        self.mutability = PointerMutability.MUT
        self.origin = PointerOrigin.EXTERNAL
        self.nullable = False

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct Array(IRBase, TypeNode):
    var kind: String
    var element: Value
    var size: Optional[Int]
    var array_kind: String
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = "Array"
        self.element = Value()
        self.size = None
        self.array_kind = ArrayKind.FIXED
        self.size_bytes = 0
        self.align_bytes = None

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct FunctionPtr(IRBase, TypeNode):
    var kind: String
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
        self.kind = "FunctionPtr"
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

    def node_kind(self) -> String:
        return self.kind

# Forward declaration trick: `Param` is defined below the Decl section but is
# referenced by `FunctionPtr`. Mojo resolves structs at module scope, so the
# full definition appearing later in the same file is fine.


@fieldwise_init
struct OpaqueRecordRef(IRBase, TypeNode):
    var kind: String
    var decl_id: String
    var name: String
    var c_name: String
    var is_union: Bool
    var size_bytes: Optional[Int]
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = "OpaqueRecordRef"
        self.decl_id = ""
        self.name = ""
        self.c_name = ""
        self.is_union = False
        self.size_bytes = None
        self.align_bytes = None

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct UnsupportedType(IRBase, TypeNode):
    var kind: String
    var category: String
    var spelling: String
    var reason: String
    var size_bytes: Optional[Int]
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = "UnsupportedType"
        self.category = UnsupportedTypeCategory.UNKNOWN
        self.spelling = ""
        self.reason = ""
        self.size_bytes = None
        self.align_bytes = None

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct ComplexType(IRBase, TypeNode):
    var kind: String
    var element: FloatType
    var size_bytes: Int
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = "ComplexType"
        self.element = FloatType()
        self.size_bytes = 0
        self.align_bytes = None

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct VectorType(IRBase, TypeNode):
    var kind: String
    var element: Value
    var count: Optional[Int]
    var size_bytes: Int
    var is_ext_vector: Bool
    var align_bytes: Optional[Int]

    def __init__(out self):
        self.kind = "VectorType"
        self.element = Value()
        self.count = None
        self.size_bytes = 0
        self.is_ext_vector = False
        self.align_bytes = None

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct StructRef(IRBase, TypeNode):
    var kind: String
    var decl_id: String
    var name: String
    var c_name: String
    var is_union: Bool
    var size_bytes: Int
    var align_bytes: Optional[Int]
    var is_anonymous: Bool

    def __init__(out self):
        self.kind = "StructRef"
        self.decl_id = ""
        self.name = ""
        self.c_name = ""
        self.is_union = False
        self.size_bytes = 0
        self.align_bytes = None
        self.is_anonymous = False

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct EnumRef(IRBase, TypeNode):
    var kind: String
    var decl_id: String
    var name: String
    var c_name: String
    var underlying: IntType

    def __init__(out self):
        self.kind = "EnumRef"
        self.decl_id = ""
        self.name = ""
        self.c_name = ""
        self.underlying = IntType()

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct TypeRef(IRBase, TypeNode):
    var kind: String
    var decl_id: String
    var name: String
    var canonical: Value

    def __init__(out self):
        self.kind = "TypeRef"
        self.decl_id = ""
        self.name = ""
        self.canonical = Value()

    def node_kind(self) -> String:
        return self.kind

# ─────────────────────────────────────────────
# ConstExpr — structured constant-expression subset.
# ─────────────────────────────────────────────

@fieldwise_init
struct IntLiteral(IRBase):
    var kind: String
    var value: Int

    def __init__(out self):
        self.kind = "IntLiteral"
        self.value = 0


@fieldwise_init
struct FloatLiteral(IRBase):
    var kind: String
    var value: Value

    def __init__(out self):
        self.kind = "FloatLiteral"
        self.value = Value()


@fieldwise_init
struct IRString(IRBase):
    var kind: String
    var value: String

    def __init__(out self):
        self.kind = "IRString"
        self.value = ""


@fieldwise_init
struct CharLiteral(IRBase):
    var kind: String
    var value: String

    def __init__(out self):
        self.kind = "CharLiteral"
        self.value = ""


@fieldwise_init
struct NullPtrLiteral(IRBase):
    var kind: String

    def __init__(out self):
        self.kind = "NullPtrLiteral"


@fieldwise_init
struct RefExpr(IRBase):
    var kind: String
    var name: String

    def __init__(out self):
        self.kind = "RefExpr"
        self.name = ""


@fieldwise_init
struct UnaryExpr(IRBase):
    var kind: String
    var op: String
    var operand: Value

    def __init__(out self):
        self.kind = "UnaryExpr"
        self.op = ""
        self.operand = Value()


@fieldwise_init
struct BinaryExpr(IRBase):
    var kind: String
    var op: String
    var lhs: Value
    var rhs: Value

    def __init__(out self):
        self.kind = "BinaryExpr"
        self.op = ""
        self.lhs = Value()
        self.rhs = Value()


@fieldwise_init
struct CastExpr(IRBase):
    var kind: String
    var target: Value
    var expr: Value

    def __init__(out self):
        self.kind = "CastExpr"
        self.target = Value()
        self.expr = Value()


@fieldwise_init
struct SizeOfExpr(IRBase):
    var kind: String
    var target: Value

    def __init__(out self):
        self.kind = "SizeOfExpr"
        self.target = Value()


@fieldwise_init
struct CallExpr(IRBase):
    var kind: String
    var callee: Value
    var args: List[Value]

    def __init__(out self):
        self.kind = "CallExpr"
        self.callee = Value()
        self.args = List[Value]()


# ─────────────────────────────────────────────
# Declaration nodes (C-facing).
# ─────────────────────────────────────────────

@fieldwise_init
struct Field(IRBase):
    var kind: String
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
        self.kind = "Field"
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
    var kind: String
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
        self.kind = "Struct"
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
    var kind: String
    var decl_id: String
    var name: String
    var c_name: String
    var underlying: IntType
    var enumerants: List[Enumerant]
    var alias_names: List[String]
    var is_anonymous: Bool
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "Enum"
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
    var kind: String
    var decl_id: String
    var name: String
    var aliased: Value
    var canonical: Value
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "Typedef"
        self.decl_id = ""
        self.name = ""
        self.aliased = Value()
        self.canonical = Value()
        self.doc = None


@fieldwise_init
struct Function(IRBase):
    var kind: String
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
        self.kind = "Function"
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
    var kind: String
    var name: String
    var type_field: Value
    var expr: Value
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "Const"
        self.name = ""
        self.type_field = Value()
        self.expr = Value()
        self.doc = None


@fieldwise_init
struct MacroDecl(IRBase):
    var kind: String
    var name: String
    var tokens: List[String]
    var macro_kind: String
    var expr: Optional[Value]
    var type_field: Optional[Value]
    var diagnostic: Optional[String]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "MacroDecl"
        self.name = ""
        self.tokens = List[String]()
        self.macro_kind = MacroDeclKind.INVALID
        self.expr = None
        self.type_field = None
        self.diagnostic = None
        self.doc = None


@fieldwise_init
struct GlobalVar(IRBase):
    var kind: String
    var decl_id: String
    var name: String
    var link_name: String
    var type_field: Value
    var is_const: Bool
    var initializer: Optional[Value]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "GlobalVar"
        self.decl_id = ""
        self.name = ""
        self.link_name = ""
        self.type_field = Value()
        self.is_const = False
        self.initializer = None
        self.doc = None


@fieldwise_init
struct Unit(IRBase):
    var kind: String
    var source_header: String
    var library: String
    var link_name: String
    var target_abi: TargetABI
    var decls: List[Value]
    var diagnostics: List[IRDiagnostic]

    def __init__(out self):
        self.kind = "Unit"
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
    var kind: String
    var name: String

    def __init__(out self):
        self.kind = "BuiltinType"
        self.name = MojoBuiltin.NONE

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct NamedType(IRBase, TypeNode):
    var kind: String
    var name: String

    def __init__(out self):
        self.kind = "NamedType"
        self.name = ""

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct DTypeArg(IRBase):
    var kind: String
    var value: String

    def __init__(out self):
        self.kind = "DTypeArg"
        self.value = ""


@fieldwise_init
struct ConstArg(IRBase):
    var kind: String
    var value: Int

    def __init__(out self):
        self.kind = "ConstArg"
        self.value = 0


@fieldwise_init
struct NameArg(IRBase):
    var kind: String
    var value: String

    def __init__(out self):
        self.kind = "NameArg"
        self.value = ""


@fieldwise_init
struct TypeArg(IRBase):
    var kind: String
    var type_field: Value

    def __init__(out self):
        self.kind = "TypeArg"
        self.type_field = Value()


@fieldwise_init
struct ParametricType(IRBase, TypeNode):
    var kind: String
    var base: String
    var args: List[Value]

    def __init__(out self):
        self.kind = "ParametricType"
        self.base = ParametricBase.SIMD
        self.args = List[Value]()

    def node_kind(self) -> String:
        return self.kind

@fieldwise_init
struct StoredMember(IRBase):
    var kind: String
    var index: Int
    var name: String
    var type_field: Value
    var byte_offset: Int
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "StoredMember"
        self.index = 0
        self.name = ""
        self.type_field = Value()
        self.byte_offset = 0
        self.doc = None


@fieldwise_init
struct PaddingMember(IRBase):
    var kind: String
    var name: String
    var size_bytes: Int
    var byte_offset: Int

    def __init__(out self):
        self.kind = "PaddingMember"
        self.name = ""
        self.size_bytes = 0
        self.byte_offset = 0


@fieldwise_init
struct OpaqueStorageMember(IRBase):
    var kind: String
    var name: String
    var size_bytes: Int

    def __init__(out self):
        self.kind = "OpaqueStorageMember"
        self.name = ""
        self.size_bytes = 0


@fieldwise_init
struct BitfieldField(IRBase):
    var kind: String
    var index: Int
    var name: String
    var logical_type: Value
    var bit_offset: Int
    var bit_width: Int
    var signed: Bool
    var bool_semantics: Bool
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "BitfieldField"
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
    var kind: String
    var storage_name: String
    var storage_type: Value
    var byte_offset: Int
    var first_index: Int
    var storage_width_bits: Int
    var fields: List[BitfieldField]

    def __init__(out self):
        self.kind = "BitfieldGroupMember"
        self.storage_name = ""
        self.storage_type = Value()
        self.byte_offset = 0
        self.first_index = 0
        self.storage_width_bits = 0
        self.fields = List[BitfieldField]()


@fieldwise_init
struct ComptimeMember(IRBase):
    var kind: String
    var name: String
    var type_value: Optional[Value]
    var const_value: Optional[Value]

    def __init__(out self):
        self.kind = "ComptimeMember"
        self.name = ""
        self.type_value = None
        self.const_value = None


@fieldwise_init
struct InitializerParam(IRBase):
    var kind: String
    var name: String
    var type_field: Value

    def __init__(out self):
        self.kind = "InitializerParam"
        self.name = ""
        self.type_field = Value()


@fieldwise_init
struct Initializer(IRBase):
    var kind: String
    var params: List[InitializerParam]

    def __init__(out self):
        self.kind = "Initializer"
        self.params = List[InitializerParam]()


@fieldwise_init
struct FlexibleTail(IRBase):
    var kind: String
    var field_name: String
    var element_type: Value
    var pattern: String
    var byte_offset: Int

    def __init__(out self):
        self.kind = "FlexibleTail"
        self.field_name = ""
        self.element_type = Value()
        self.pattern = ""
        self.byte_offset = 0


@fieldwise_init
struct StructDecl(IRBase):
    var kind: String
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
        self.kind = "StructDecl"
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
    var kind: String
    var alias_kind: String
    var name: String
    var type_value: Optional[Value]
    var const_type: Optional[Value]
    var const_value: Optional[Value]
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "AliasDecl"
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
    var kind: String
    var link_mode: String
    var symbol: String

    def __init__(out self):
        self.kind = "CallTarget"
        self.link_mode = LinkMode.EXTERNAL_CALL
        self.symbol = ""


@fieldwise_init
struct FunctionDecl(IRBase):
    var kind: String
    var function_kind: String
    var name: String
    var link_name: String
    var params: List[Param]
    var return_type: Value
    var call_target: CallTarget
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "FunctionDecl"
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
    var kind: String
    var global_kind: String
    var name: String
    var link_name: String
    var value_type: Value
    var is_const: Bool
    var diagnostics: List[MappingNote]
    var doc: Optional[DocComment]

    def __init__(out self):
        self.kind = "GlobalDecl"
        self.global_kind = GlobalKind.WRAPPER
        self.name = ""
        self.link_name = ""
        self.value_type = Value()
        self.is_const = False
        self.diagnostics = List[MappingNote]()
        self.doc = None


@fieldwise_init
struct MojoModule(IRBase):
    var kind: String
    var source_header: String
    var library: String
    var link_name: String
    var link_mode: String
    var library_path_hint: Optional[String]
    var dependencies: ModuleDependencies
    var decls: List[Value]

    def __init__(out self):
        self.kind = "MojoModule"
        self.source_header = ""
        self.library = ""
        self.link_name = ""
        self.link_mode = LinkMode.EXTERNAL_CALL
        self.library_path_hint = None
        self.dependencies = ModuleDependencies()
        self.decls = List[Value]()


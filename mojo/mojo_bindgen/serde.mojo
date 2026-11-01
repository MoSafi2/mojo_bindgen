"""Current-model CIR and MojoIR debug codecs. JSON is unversioned and stage-checked."""

from std.memory import ArcPointer
from .ir import *
from ._numbers import IntegerValue
from ._debug_json import JSON, node, parse_json, dump_json


def _fields(value: JSON, kind: String, allowed: String) raises -> ArcPointer[JSON]:
    value.check_fields("|kind|fields|")
    if value.get("kind").ptr()[].text() != kind:
        raise Error("expected " + kind)
    var fields = value.get("fields")
    fields.ptr()[].check_fields(allowed)
    return fields^


def _decode_intkind(value: JSON) raises -> IntKind:
    var text = value.text()
    match text:
        case "BOOL":
            return IntKind.BOOL
        case "CHAR_S":
            return IntKind.CHAR_S
        case "CHAR_U":
            return IntKind.CHAR_U
        case "SCHAR":
            return IntKind.SCHAR
        case "UCHAR":
            return IntKind.UCHAR
        case "SHORT":
            return IntKind.SHORT
        case "USHORT":
            return IntKind.USHORT
        case "INT":
            return IntKind.INT
        case "UINT":
            return IntKind.UINT
        case "LONG":
            return IntKind.LONG
        case "ULONG":
            return IntKind.ULONG
        case "LONGLONG":
            return IntKind.LONGLONG
        case "ULONGLONG":
            return IntKind.ULONGLONG
        case "INT128":
            return IntKind.INT128
        case "UINT128":
            return IntKind.UINT128
        case "WCHAR":
            return IntKind.WCHAR
        case "CHAR16":
            return IntKind.CHAR16
        case "CHAR32":
            return IntKind.CHAR32
        case "EXT_INT":
            return IntKind.EXT_INT
        case _:
            raise Error("invalid IntKind: " + text)


def _decode_floatkind(value: JSON) raises -> FloatKind:
    var text = value.text()
    match text:
        case "FLOAT16":
            return FloatKind.FLOAT16
        case "FLOAT":
            return FloatKind.FLOAT
        case "DOUBLE":
            return FloatKind.DOUBLE
        case "LONG_DOUBLE":
            return FloatKind.LONG_DOUBLE
        case "FLOAT128":
            return FloatKind.FLOAT128
        case _:
            raise Error("invalid FloatKind: " + text)


def _decode_pointermutability(value: JSON) raises -> PointerMutability:
    var text = value.text()
    match text:
        case "mut":
            return PointerMutability.MUT
        case "immut":
            return PointerMutability.IMMUT
        case _:
            raise Error("invalid PointerMutability: " + text)


def _decode_pointerorigin(value: JSON) raises -> PointerOrigin:
    var text = value.text()
    match text:
        case "external":
            return PointerOrigin.EXTERNAL
        case "any":
            return PointerOrigin.ANY
        case _:
            raise Error("invalid PointerOrigin: " + text)


def _decode_inlinedisposition(value: JSON) raises -> InlineDisposition:
    var text = value.text()
    match text:
        case "none":
            return InlineDisposition.NONE
        case "inline":
            return InlineDisposition.INLINE
        case "extern_inline":
            return InlineDisposition.EXTERN_INLINE
        case _:
            raise Error("invalid InlineDisposition: " + text)


def _decode_byteorder(value: JSON) raises -> ByteOrder:
    var text = value.text()
    match text:
        case "little":
            return ByteOrder.LITTLE
        case "big":
            return ByteOrder.BIG
        case _:
            raise Error("invalid ByteOrder: " + text)


def _decode_mojobuiltin(value: JSON) raises -> MojoBuiltin:
    var text = value.text()
    match text:
        case "NoneType":
            return MojoBuiltin.NONE
        case "Bool":
            return MojoBuiltin.BOOL
        case "Int8":
            return MojoBuiltin.INT8
        case "UInt8":
            return MojoBuiltin.UINT8
        case "Int128":
            return MojoBuiltin.INT128
        case "UInt128":
            return MojoBuiltin.UINT128
        case "Float16":
            return MojoBuiltin.FLOAT16
        case "c_char":
            return MojoBuiltin.C_CHAR
        case "c_uchar":
            return MojoBuiltin.C_UCHAR
        case "c_short":
            return MojoBuiltin.C_SHORT
        case "c_ushort":
            return MojoBuiltin.C_USHORT
        case "c_int":
            return MojoBuiltin.C_INT
        case "c_uint":
            return MojoBuiltin.C_UINT
        case "c_long":
            return MojoBuiltin.C_LONG
        case "c_ulong":
            return MojoBuiltin.C_ULONG
        case "c_long_long":
            return MojoBuiltin.C_LONG_LONG
        case "c_ulong_long":
            return MojoBuiltin.C_ULONG_LONG
        case "c_float":
            return MojoBuiltin.C_FLOAT
        case "c_double":
            return MojoBuiltin.C_DOUBLE
        case "unsupported":
            return MojoBuiltin.UNSUPPORTED
        case _:
            raise Error("invalid MojoBuiltin: " + text)


def _decode_globalkind(value: JSON) raises -> GlobalKind:
    var text = value.text()
    match text:
        case "wrapper":
            return GlobalKind.WRAPPER
        case "stub":
            return GlobalKind.STUB
        case _:
            raise Error("invalid GlobalKind: " + text)


def _decode_functionkind(value: JSON) raises -> FunctionKind:
    var text = value.text()
    match text:
        case "wrapper":
            return FunctionKind.WRAPPER
        case "extern_declaration":
            return FunctionKind.EXTERN_DECLARATION
        case "variadic_stub":
            return FunctionKind.VARIADIC_STUB
        case "directive_stub":
            return FunctionKind.DIRECTIVE_STUB
        case "non_register_return_stub":
            return FunctionKind.NON_REGISTER_RETURN_STUB
        case _:
            raise Error("invalid FunctionKind: " + text)


def _decode_linkmode(value: JSON) raises -> LinkMode:
    var text = value.text()
    match text:
        case "external_call":
            return LinkMode.EXTERNAL_CALL
        case "owned_dl_handle":
            return LinkMode.OWNED_DL_HANDLE
        case _:
            raise Error("invalid LinkMode: " + text)


def _decode_mappingseverity(value: JSON) raises -> MappingSeverity:
    var text = value.text()
    match text:
        case "note":
            return MappingSeverity.NOTE
        case "warning":
            return MappingSeverity.WARNING
        case "error":
            return MappingSeverity.ERROR
        case _:
            raise Error("invalid MappingSeverity: " + text)


def _decode_supportdeclkind(value: JSON) raises -> SupportDeclKind:
    var text = value.text()
    match text:
        case "dl_handle_helpers":
            return SupportDeclKind.DL_HANDLE_HELPERS
        case "global_symbol_helpers":
            return SupportDeclKind.GLOBAL_SYMBOL_HELPERS
        case "variadic_helpers":
            return SupportDeclKind.VARIADIC_HELPERS
        case _:
            raise Error("invalid SupportDeclKind: " + text)


def _decode_parametricbase(value: JSON) raises -> ParametricBase:
    var text = value.text()
    match text:
        case "SIMD":
            return ParametricBase.SIMD
        case "ComplexSIMD":
            return ParametricBase.COMPLEX_SIMD
        case "Atomic":
            return ParametricBase.ATOMIC
        case "UnsafeUnion":
            return ParametricBase.UNSAFE_UNION
        case _:
            raise Error("invalid ParametricBase: " + text)


def _decode_structtraits(value: JSON) raises -> StructTraits:
    var text = value.text()
    match text:
        case "not Movable":
            return StructTraits.NOT_MOVABLE
        case "Copyable":
            return StructTraits.COPYABLE
        case "ImplicitlyCopyable":
            return StructTraits.IMPLICITLY_COPYABLE
        case "Movable":
            return StructTraits.MOVABLE
        case "RegisterPassable":
            return StructTraits.REGISTER_PASSABLE
        case "TrivialRegisterPassable":
            return StructTraits.TRIVIAL_REGISTER_PASSABLE
        case _:
            raise Error("invalid StructTraits: " + text)


def _decode_structkind(value: JSON) raises -> StructKind:
    var text = value.text()
    match text:
        case "plain":
            return StructKind.PLAIN
        case "opaque":
            return StructKind.OPAQUE
        case _:
            raise Error("invalid StructKind: " + text)


def _decode_mojopassability(value: JSON) raises -> MojoPassability:
    var text = value.text()
    match text:
        case "memory_only":
            return MojoPassability.MEMORY_ONLY
        case "register_passable":
            return MojoPassability.REGISTER_PASSABLE
        case "trivial_register_passable":
            return MojoPassability.TRIVIAL_REGISTER_PASSABLE
        case _:
            raise Error("invalid MojoPassability: " + text)


def _decode_aliaskind(value: JSON) raises -> AliasKind:
    var text = value.text()
    match text:
        case "type_alias":
            return AliasKind.TYPE_ALIAS
        case "callback_signature":
            return AliasKind.CALLBACK_SIGNATURE
        case "union_layout":
            return AliasKind.UNION_LAYOUT
        case "const_value":
            return AliasKind.CONST_VALUE
        case "macro_value":
            return AliasKind.MACRO_VALUE
        case _:
            raise Error("invalid AliasKind: " + text)


def _decode_primitivekind(value: JSON) raises -> PrimitiveKind:
    var text = value.text()
    match text:
        case "BOOL":
            return PrimitiveKind.int_kind(IntKind.BOOL)
        case "CHAR_S":
            return PrimitiveKind.int_kind(IntKind.CHAR_S)
        case "CHAR_U":
            return PrimitiveKind.int_kind(IntKind.CHAR_U)
        case "SCHAR":
            return PrimitiveKind.int_kind(IntKind.SCHAR)
        case "UCHAR":
            return PrimitiveKind.int_kind(IntKind.UCHAR)
        case "SHORT":
            return PrimitiveKind.int_kind(IntKind.SHORT)
        case "USHORT":
            return PrimitiveKind.int_kind(IntKind.USHORT)
        case "INT":
            return PrimitiveKind.int_kind(IntKind.INT)
        case "UINT":
            return PrimitiveKind.int_kind(IntKind.UINT)
        case "LONG":
            return PrimitiveKind.int_kind(IntKind.LONG)
        case "ULONG":
            return PrimitiveKind.int_kind(IntKind.ULONG)
        case "LONGLONG":
            return PrimitiveKind.int_kind(IntKind.LONGLONG)
        case "ULONGLONG":
            return PrimitiveKind.int_kind(IntKind.ULONGLONG)
        case "INT128":
            return PrimitiveKind.int_kind(IntKind.INT128)
        case "UINT128":
            return PrimitiveKind.int_kind(IntKind.UINT128)
        case "WCHAR":
            return PrimitiveKind.int_kind(IntKind.WCHAR)
        case "CHAR16":
            return PrimitiveKind.int_kind(IntKind.CHAR16)
        case "CHAR32":
            return PrimitiveKind.int_kind(IntKind.CHAR32)
        case "EXT_INT":
            return PrimitiveKind.int_kind(IntKind.EXT_INT)
        case "FLOAT16":
            return PrimitiveKind.float_kind(FloatKind.FLOAT16)
        case "FLOAT":
            return PrimitiveKind.float_kind(FloatKind.FLOAT)
        case "DOUBLE":
            return PrimitiveKind.float_kind(FloatKind.DOUBLE)
        case "LONG_DOUBLE":
            return PrimitiveKind.float_kind(FloatKind.LONG_DOUBLE)
        case "FLOAT128":
            return PrimitiveKind.float_kind(FloatKind.FLOAT128)
        case _:
            raise Error("invalid primitive kind")


def _decode_arraykind(value: JSON) raises -> ArrayKind:
    var text = value.text()
    match text:
        case "fixed":
            return ArrayKind.fixed
        case "incomplete":
            return ArrayKind.incomplete
        case "flexible":
            return ArrayKind.flexible
        case "variable":
            return ArrayKind.variable
        case _:
            raise Error("invalid ArrayKind: " + text)


def _decode_unsupportedtypecategory(value: JSON) raises -> UnsupportedTypeCategory:
    var text = value.text()
    match text:
        case "unexposed":
            return UnsupportedTypeCategory.unexposed
        case "vector":
            return UnsupportedTypeCategory.vector
        case "complex":
            return UnsupportedTypeCategory.complex
        case "block":
            return UnsupportedTypeCategory.block
        case "objc":
            return UnsupportedTypeCategory.objc
        case "unsupported_extension":
            return UnsupportedTypeCategory.unsupported_extension
        case "invalid":
            return UnsupportedTypeCategory.invalid
        case "unknown":
            return UnsupportedTypeCategory.unknown
        case _:
            raise Error("invalid UnsupportedTypeCategory: " + text)


def _decode_fampattern(value: JSON) raises -> FamPattern:
    var text = value.text()
    match text:
        case "c99_empty":
            return FamPattern.c99_empty
        case "gnu_zero":
            return FamPattern.gnu_zero
        case _:
            raise Error("invalid FamPattern: " + text)


def _decode_macrodeclkind(value: JSON) raises -> MacroDeclKind:
    var text = value.text()
    match text:
        case "object_like_supported":
            return MacroDeclKind.object_like_supported
        case "object_like_unsupported":
            return MacroDeclKind.object_like_unsupported
        case "function_like_unsupported":
            return MacroDeclKind.function_like_unsupported
        case "empty":
            return MacroDeclKind.empty
        case "predefined":
            return MacroDeclKind.predefined
        case "invalid":
            return MacroDeclKind.invalid
        case _:
            raise Error("invalid MacroDeclKind: " + text)


def _decode_list_arcpointer_cconstexpr(value: JSON) raises -> List[ArcPointer[CConstExpr]]:
    var result = List[ArcPointer[CConstExpr]]()
    for child in value.items():
        result.append(ArcPointer(decode_c_expr(child.ptr()[])))
    return result^


def _encode_list_arcpointer_cconstexpr(value: List[ArcPointer[CConstExpr]]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(encode_c_expr(child.ptr()[])))
    return JSON.array(result^)


def _decode_list_arcpointer_mojoconstexpr(value: JSON) raises -> List[ArcPointer[MojoConstExpr]]:
    var result = List[ArcPointer[MojoConstExpr]]()
    for child in value.items():
        result.append(ArcPointer(decode_mojo_expr(child.ptr()[])))
    return result^


def _encode_list_arcpointer_mojoconstexpr(value: List[ArcPointer[MojoConstExpr]]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(encode_mojo_expr(child.ptr()[])))
    return JSON.array(result^)


def _decode_list_bitfieldfield(value: JSON) raises -> List[BitfieldField]:
    var result = List[BitfieldField]()
    for child in value.items():
        result.append(_decode_bitfieldfield(child.ptr()[]))
    return result^


def _encode_list_bitfieldfield(value: List[BitfieldField]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_bitfieldfield(child)))
    return JSON.array(result^)


def _decode_list_cparam(value: JSON) raises -> List[CParam]:
    var result = List[CParam]()
    for child in value.items():
        result.append(_decode_cparam(child.ptr()[]))
    return result^


def _encode_list_cparam(value: List[CParam]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_cparam(child)))
    return JSON.array(result^)


def _decode_list_comptimemember(value: JSON) raises -> List[ComptimeMember]:
    var result = List[ComptimeMember]()
    for child in value.items():
        result.append(_decode_comptimemember(child.ptr()[]))
    return result^


def _encode_list_comptimemember(value: List[ComptimeMember]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_comptimemember(child)))
    return JSON.array(result^)


def _decode_list_decl(value: JSON) raises -> List[Decl]:
    var result = List[Decl]()
    for child in value.items():
        result.append(decode_decl(child.ptr()[]))
    return result^


def _encode_list_decl(value: List[Decl]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(encode_decl(child)))
    return JSON.array(result^)


def _decode_list_enumerant(value: JSON) raises -> List[Enumerant]:
    var result = List[Enumerant]()
    for child in value.items():
        result.append(_decode_enumerant(child.ptr()[]))
    return result^


def _encode_list_enumerant(value: List[Enumerant]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_enumerant(child)))
    return JSON.array(result^)


def _decode_list_field(value: JSON) raises -> List[Field]:
    var result = List[Field]()
    for child in value.items():
        result.append(_decode_field(child.ptr()[]))
    return result^


def _encode_list_field(value: List[Field]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_field(child)))
    return JSON.array(result^)


def _decode_list_irdiagnostic(value: JSON) raises -> List[IRDiagnostic]:
    var result = List[IRDiagnostic]()
    for child in value.items():
        result.append(_decode_irdiagnostic(child.ptr()[]))
    return result^


def _encode_list_irdiagnostic(value: List[IRDiagnostic]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_irdiagnostic(child)))
    return JSON.array(result^)


def _decode_list_initializerparam(value: JSON) raises -> List[InitializerParam]:
    var result = List[InitializerParam]()
    for child in value.items():
        result.append(_decode_initializerparam(child.ptr()[]))
    return result^


def _encode_list_initializerparam(value: List[InitializerParam]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_initializerparam(child)))
    return JSON.array(result^)


def _decode_list_initializer(value: JSON) raises -> List[Initializer]:
    var result = List[Initializer]()
    for child in value.items():
        result.append(_decode_initializer(child.ptr()[]))
    return result^


def _encode_list_initializer(value: List[Initializer]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_initializer(child)))
    return JSON.array(result^)


def _decode_list_mappingnote(value: JSON) raises -> List[MappingNote]:
    var result = List[MappingNote]()
    for child in value.items():
        result.append(_decode_mappingnote(child.ptr()[]))
    return result^


def _encode_list_mappingnote(value: List[MappingNote]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_mappingnote(child)))
    return JSON.array(result^)


def _decode_list_moduleimport(value: JSON) raises -> List[ModuleImport]:
    var result = List[ModuleImport]()
    for child in value.items():
        result.append(_decode_moduleimport(child.ptr()[]))
    return result^


def _encode_list_moduleimport(value: List[ModuleImport]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_moduleimport(child)))
    return JSON.array(result^)


def _decode_list_mojodecl(value: JSON) raises -> List[MojoDecl]:
    var result = List[MojoDecl]()
    for child in value.items():
        result.append(decode_mojo_decl(child.ptr()[]))
    return result^


def _encode_list_mojodecl(value: List[MojoDecl]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(encode_mojo_decl(child)))
    return JSON.array(result^)


def _decode_list_mojoparam(value: JSON) raises -> List[MojoParam]:
    var result = List[MojoParam]()
    for child in value.items():
        result.append(_decode_mojoparam(child.ptr()[]))
    return result^


def _encode_list_mojoparam(value: List[MojoParam]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_mojoparam(child)))
    return JSON.array(result^)


def _decode_list_parametricarg(value: JSON) raises -> List[ParametricArg]:
    var result = List[ParametricArg]()
    for child in value.items():
        result.append(decode_parametric_arg(child.ptr()[]))
    return result^


def _encode_list_parametricarg(value: List[ParametricArg]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(encode_parametric_arg(child)))
    return JSON.array(result^)


def _decode_list_string(value: JSON) raises -> List[String]:
    var result = List[String]()
    for child in value.items():
        result.append(child.ptr()[].text())
    return result^


def _encode_list_string(value: List[String]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(JSON.string(child.copy())))
    return JSON.array(result^)


def _decode_list_structmember(value: JSON) raises -> List[StructMember]:
    var result = List[StructMember]()
    for child in value.items():
        result.append(decode_struct_member(child.ptr()[]))
    return result^


def _encode_list_structmember(value: List[StructMember]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(encode_struct_member(child)))
    return JSON.array(result^)


def _decode_list_structtraits(value: JSON) raises -> List[StructTraits]:
    var result = List[StructTraits]()
    for child in value.items():
        result.append(_decode_structtraits(child.ptr()[]))
    return result^


def _encode_list_structtraits(value: List[StructTraits]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(JSON.string(child.value())))
    return JSON.array(result^)


def _decode_list_supportdecl(value: JSON) raises -> List[SupportDecl]:
    var result = List[SupportDecl]()
    for child in value.items():
        result.append(_decode_supportdecl(child.ptr()[]))
    return result^


def _encode_list_supportdecl(value: List[SupportDecl]) -> JSON:
    var result = List[ArcPointer[JSON]]()
    for child in value:
        result.append(ArcPointer(_encode_supportdecl(child)))
    return JSON.array(result^)


def _decode_optional_arcpointer_cconstexpr(value: JSON) raises -> Optional[ArcPointer[CConstExpr]]:
    if value.is_null():
        return {}
    return ArcPointer(decode_c_expr(value))


def _encode_optional_arcpointer_cconstexpr(value: Optional[ArcPointer[CConstExpr]]) -> JSON:
    if value:
        return encode_c_expr(value.value().ptr()[])
    return materialize[JSON.null]()


def _decode_optional_arcpointer_ctype(value: JSON) raises -> Optional[ArcPointer[CType]]:
    if value.is_null():
        return {}
    return ArcPointer(decode_c_type(value))


def _encode_optional_arcpointer_ctype(value: Optional[ArcPointer[CType]]) -> JSON:
    if value:
        return encode_c_type(value.value().ptr()[])
    return materialize[JSON.null]()


def _decode_optional_arcpointer_mojoconstexpr(
    value: JSON,
) raises -> Optional[ArcPointer[MojoConstExpr]]:
    if value.is_null():
        return {}
    return ArcPointer(decode_mojo_expr(value))


def _encode_optional_arcpointer_mojoconstexpr(value: Optional[ArcPointer[MojoConstExpr]]) -> JSON:
    if value:
        return encode_mojo_expr(value.value().ptr()[])
    return materialize[JSON.null]()


def _decode_optional_arcpointer_mojotype(value: JSON) raises -> Optional[ArcPointer[MojoType]]:
    if value.is_null():
        return {}
    return ArcPointer(decode_mojo_type(value))


def _encode_optional_arcpointer_mojotype(value: Optional[ArcPointer[MojoType]]) -> JSON:
    if value:
        return encode_mojo_type(value.value().ptr()[])
    return materialize[JSON.null]()


def _decode_optional_doccomment(value: JSON) raises -> Optional[DocComment]:
    if value.is_null():
        return {}
    return _decode_doccomment(value)


def _encode_optional_doccomment(value: Optional[DocComment]) -> JSON:
    if value:
        return _encode_doccomment(value.value())
    return materialize[JSON.null]()


def _decode_optional_fampattern(value: JSON) raises -> Optional[FamPattern]:
    if value.is_null():
        return {}
    return _decode_fampattern(value)


def _encode_optional_fampattern(value: Optional[FamPattern]) -> JSON:
    if value:
        return JSON.string(value.value().value())
    return materialize[JSON.null]()


def _decode_optional_flexibletail(value: JSON) raises -> Optional[FlexibleTail]:
    if value.is_null():
        return {}
    return _decode_flexibletail(value)


def _encode_optional_flexibletail(value: Optional[FlexibleTail]) -> JSON:
    if value:
        return _encode_flexibletail(value.value())
    return materialize[JSON.null]()


def _decode_optional_int(value: JSON) raises -> Optional[Int]:
    if value.is_null():
        return {}
    return value.int_value()


def _encode_optional_int(value: Optional[Int]) -> JSON:
    if value:
        return JSON.integer(value.value())
    return materialize[JSON.null]()


def _decode_optional_list_string(value: JSON) raises -> Optional[List[String]]:
    if value.is_null():
        return {}
    return _decode_list_string(value)


def _encode_optional_list_string(value: Optional[List[String]]) -> JSON:
    if value:
        return _encode_list_string(value.value())
    return materialize[JSON.null]()


def _decode_optional_string(value: JSON) raises -> Optional[String]:
    if value.is_null():
        return {}
    return value.text()


def _encode_optional_string(value: Optional[String]) -> JSON:
    if value:
        return JSON.string(value.value().copy())
    return materialize[JSON.null]()


def _decode_doccomment(value: JSON) raises -> DocComment:
    var fields = _fields(value, "DocComment", "|text|brief|source|")
    var v_text = fields.ptr()[].get("text").ptr()[].text()
    var v_brief: Optional[String] = {}
    if fields.ptr()[].has("brief"):
        v_brief = _decode_optional_string(fields.ptr()[].get("brief").ptr()[])
    var v_source: String = "clang_raw"
    if fields.ptr()[].has("source"):
        v_source = fields.ptr()[].get("source").ptr()[].text()
    if v_source != "clang_raw":
        raise Error("invalid source")
    return DocComment(v_text^, v_brief^, v_source^)


def _encode_doccomment(value: DocComment) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["text"] = ArcPointer(JSON.string(value.text.copy()))
    fields["brief"] = ArcPointer(_encode_optional_string(value.brief))
    fields["source"] = ArcPointer(JSON.string(value.source.copy()))
    return node("DocComment", fields^)


def _decode_qualifiers(value: JSON) raises -> Qualifiers:
    var fields = _fields(value, "Qualifiers", "|is_const|is_volatile|is_restrict|")
    var v_is_const: Bool = False
    if fields.ptr()[].has("is_const"):
        v_is_const = fields.ptr()[].get("is_const").ptr()[].bool_value()
    var v_is_volatile: Bool = False
    if fields.ptr()[].has("is_volatile"):
        v_is_volatile = fields.ptr()[].get("is_volatile").ptr()[].bool_value()
    var v_is_restrict: Bool = False
    if fields.ptr()[].has("is_restrict"):
        v_is_restrict = fields.ptr()[].get("is_restrict").ptr()[].bool_value()
    return Qualifiers(v_is_const, v_is_volatile, v_is_restrict)


def _encode_qualifiers(value: Qualifiers) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["is_const"] = ArcPointer(JSON.boolean(value.is_const))
    fields["is_volatile"] = ArcPointer(JSON.boolean(value.is_volatile))
    fields["is_restrict"] = ArcPointer(JSON.boolean(value.is_restrict))
    return node("Qualifiers", fields^)


def _decode_voidtype(value: JSON) raises -> VoidType:
    var fields = _fields(value, "VoidType", "||")
    return VoidType()


def _encode_voidtype(value: VoidType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    return node("VoidType", fields^)


def _decode_inttype(value: JSON) raises -> IntType:
    var fields = _fields(value, "IntType", "|int_kind|size_bytes|align_bytes|ext_bits|")
    var v_int_kind = _decode_intkind(fields.ptr()[].get("int_kind").ptr()[])
    var v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    var v_ext_bits: Optional[Int] = {}
    if fields.ptr()[].has("ext_bits"):
        v_ext_bits = _decode_optional_int(fields.ptr()[].get("ext_bits").ptr()[])
    return IntType(v_int_kind^, v_size_bytes, v_align_bytes^, v_ext_bits^)


def _encode_inttype(value: IntType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["int_kind"] = ArcPointer(JSON.string(value.int_kind.value()))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    fields["ext_bits"] = ArcPointer(_encode_optional_int(value.ext_bits))
    return node("IntType", fields^)


def _decode_floattype(value: JSON) raises -> FloatType:
    var fields = _fields(value, "FloatType", "|float_kind|size_bytes|align_bytes|")
    var v_float_kind = _decode_floatkind(fields.ptr()[].get("float_kind").ptr()[])
    var v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    return FloatType(v_float_kind^, v_size_bytes, v_align_bytes^)


def _encode_floattype(value: FloatType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["float_kind"] = ArcPointer(JSON.string(value.float_kind.value()))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    return node("FloatType", fields^)


def _decode_qualifiedtype(value: JSON) raises -> QualifiedType:
    var fields = _fields(value, "QualifiedType", "|unqualified|qualifiers|")
    var v_unqualified = ArcPointer(decode_c_type(fields.ptr()[].get("unqualified").ptr()[]))
    var v_qualifiers: Qualifiers = Qualifiers()
    if fields.ptr()[].has("qualifiers"):
        v_qualifiers = _decode_qualifiers(fields.ptr()[].get("qualifiers").ptr()[])
    return QualifiedType(v_unqualified^, v_qualifiers^)


def _encode_qualifiedtype(value: QualifiedType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["unqualified"] = ArcPointer(encode_c_type(value.unqualified.ptr()[]))
    fields["qualifiers"] = ArcPointer(_encode_qualifiers(value.qualifiers))
    return node("QualifiedType", fields^)


def _decode_atomictype(value: JSON) raises -> AtomicType:
    var fields = _fields(value, "AtomicType", "|value_type|size_bytes|align_bytes|")
    var v_value_type = ArcPointer(decode_c_type(fields.ptr()[].get("value_type").ptr()[]))
    var v_size_bytes: Optional[Int] = {}
    if fields.ptr()[].has("size_bytes"):
        v_size_bytes = _decode_optional_int(fields.ptr()[].get("size_bytes").ptr()[])
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    return AtomicType(v_value_type^, v_size_bytes^, v_align_bytes^)


def _encode_atomictype(value: AtomicType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["value_type"] = ArcPointer(encode_c_type(value.value_type.ptr()[]))
    fields["size_bytes"] = ArcPointer(_encode_optional_int(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    return node("AtomicType", fields^)


def _decode_cpointer(value: JSON) raises -> CPointer:
    var fields = _fields(value, "CPointer", "|pointee|size_bytes|align_bytes|")
    var v_pointee = _decode_optional_arcpointer_ctype(fields.ptr()[].get("pointee").ptr()[])
    var v_size_bytes: Int = 0
    if fields.ptr()[].has("size_bytes"):
        v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    return CPointer(v_pointee^, v_size_bytes, v_align_bytes^)


def _encode_cpointer(value: CPointer) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["pointee"] = ArcPointer(_encode_optional_arcpointer_ctype(value.pointee))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    return node("CPointer", fields^)


def _decode_mojopointer(value: JSON) raises -> MojoPointer:
    var fields = _fields(value, "MojoPointer", "|pointee|mutability|origin|nullable|")
    var v_pointee = _decode_optional_arcpointer_mojotype(fields.ptr()[].get("pointee").ptr()[])
    var v_mutability: PointerMutability = PointerMutability.MUT
    if fields.ptr()[].has("mutability"):
        v_mutability = _decode_pointermutability(fields.ptr()[].get("mutability").ptr()[])
    var v_origin: PointerOrigin = PointerOrigin.EXTERNAL
    if fields.ptr()[].has("origin"):
        v_origin = _decode_pointerorigin(fields.ptr()[].get("origin").ptr()[])
    var v_nullable: Bool = False
    if fields.ptr()[].has("nullable"):
        v_nullable = fields.ptr()[].get("nullable").ptr()[].bool_value()
    return MojoPointer(v_pointee^, v_mutability^, v_origin^, v_nullable)


def _encode_mojopointer(value: MojoPointer) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["pointee"] = ArcPointer(_encode_optional_arcpointer_mojotype(value.pointee))
    fields["mutability"] = ArcPointer(JSON.string(value.mutability.value()))
    fields["origin"] = ArcPointer(JSON.string(value.origin.value()))
    fields["nullable"] = ArcPointer(JSON.boolean(value.nullable))
    return node("MojoPointer", fields^)


def _decode_carray(value: JSON) raises -> CArray:
    var fields = _fields(value, "CArray", "|element|size|array_kind|size_bytes|align_bytes|")
    var v_element = ArcPointer(decode_c_type(fields.ptr()[].get("element").ptr()[]))
    var v_size = _decode_optional_int(fields.ptr()[].get("size").ptr()[])
    var v_array_kind: ArrayKind = ArrayKind.fixed
    if fields.ptr()[].has("array_kind"):
        v_array_kind = _decode_arraykind(fields.ptr()[].get("array_kind").ptr()[])
    var v_size_bytes: Int = 0
    if fields.ptr()[].has("size_bytes"):
        v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    return CArray(v_element^, v_size^, v_array_kind^, v_size_bytes, v_align_bytes^)


def _encode_carray(value: CArray) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["element"] = ArcPointer(encode_c_type(value.element.ptr()[]))
    fields["size"] = ArcPointer(_encode_optional_int(value.size))
    fields["array_kind"] = ArcPointer(JSON.string(value.array_kind.value()))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    return node("CArray", fields^)


def _decode_mojoarray(value: JSON) raises -> MojoArray:
    var fields = _fields(value, "MojoArray", "|element|size|")
    var v_element = ArcPointer(decode_mojo_type(fields.ptr()[].get("element").ptr()[]))
    var v_size = fields.ptr()[].get("size").ptr()[].int_value()
    return MojoArray(v_element^, v_size)


def _encode_mojoarray(value: MojoArray) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["element"] = ArcPointer(encode_mojo_type(value.element.ptr()[]))
    fields["size"] = ArcPointer(JSON.integer(value.size))
    return node("MojoArray", fields^)


def _decode_cfunctionptr(value: JSON) raises -> CFunctionPtr:
    var fields = _fields(
        value,
        "CFunctionPtr",
        "|ret|params|param_names|is_variadic|calling_convention|is_noreturn|size_bytes|align_bytes|",
    )
    var v_ret = ArcPointer(decode_c_type(fields.ptr()[].get("ret").ptr()[]))
    var v_params = _decode_list_cparam(fields.ptr()[].get("params").ptr()[])
    var v_param_names: Optional[List[String]] = {}
    if fields.ptr()[].has("param_names"):
        v_param_names = _decode_optional_list_string(fields.ptr()[].get("param_names").ptr()[])
    var v_is_variadic: Bool = False
    if fields.ptr()[].has("is_variadic"):
        v_is_variadic = fields.ptr()[].get("is_variadic").ptr()[].bool_value()
    var v_calling_convention: Optional[String] = {}
    if fields.ptr()[].has("calling_convention"):
        v_calling_convention = _decode_optional_string(
            fields.ptr()[].get("calling_convention").ptr()[]
        )
    var v_is_noreturn: Bool = False
    if fields.ptr()[].has("is_noreturn"):
        v_is_noreturn = fields.ptr()[].get("is_noreturn").ptr()[].bool_value()
    var v_size_bytes: Int = 0
    if fields.ptr()[].has("size_bytes"):
        v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    return CFunctionPtr(
        v_ret^,
        v_params^,
        v_param_names^,
        v_is_variadic,
        v_calling_convention^,
        v_is_noreturn,
        v_size_bytes,
        v_align_bytes^,
    )


def _encode_cfunctionptr(value: CFunctionPtr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["ret"] = ArcPointer(encode_c_type(value.ret.ptr()[]))
    fields["params"] = ArcPointer(_encode_list_cparam(value.params))
    fields["param_names"] = ArcPointer(_encode_optional_list_string(value.param_names))
    fields["is_variadic"] = ArcPointer(JSON.boolean(value.is_variadic))
    fields["calling_convention"] = ArcPointer(_encode_optional_string(value.calling_convention))
    fields["is_noreturn"] = ArcPointer(JSON.boolean(value.is_noreturn))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    return node("CFunctionPtr", fields^)


def _decode_mojofunctionptr(value: JSON) raises -> MojoFunctionPtr:
    var fields = _fields(value, "MojoFunctionPtr", "|ret|params|abi|thin|raises|")
    var v_ret = ArcPointer(decode_mojo_type(fields.ptr()[].get("ret").ptr()[]))
    var v_params = _decode_list_mojoparam(fields.ptr()[].get("params").ptr()[])
    var v_abi: String = "C"
    if fields.ptr()[].has("abi"):
        v_abi = fields.ptr()[].get("abi").ptr()[].text()
    var v_thin: Bool = True
    if fields.ptr()[].has("thin"):
        v_thin = fields.ptr()[].get("thin").ptr()[].bool_value()
    var v_raises: Bool = False
    if fields.ptr()[].has("raises"):
        v_raises = fields.ptr()[].get("raises").ptr()[].bool_value()
    return MojoFunctionPtr(v_ret^, v_params^, v_abi^, v_thin, v_raises)


def _encode_mojofunctionptr(value: MojoFunctionPtr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["ret"] = ArcPointer(encode_mojo_type(value.ret.ptr()[]))
    fields["params"] = ArcPointer(_encode_list_mojoparam(value.params))
    fields["abi"] = ArcPointer(JSON.string(value.abi.copy()))
    fields["thin"] = ArcPointer(JSON.boolean(value.thin))
    fields["raises"] = ArcPointer(JSON.boolean(value.raises_error))
    return node("MojoFunctionPtr", fields^)


def _decode_functionattrs(value: JSON) raises -> FunctionAttrs:
    var fields = _fields(value, "FunctionAttrs", "|inline_disposition|is_noreturn|")
    var v_inline_disposition: InlineDisposition = InlineDisposition.NONE
    if fields.ptr()[].has("inline_disposition"):
        v_inline_disposition = _decode_inlinedisposition(
            fields.ptr()[].get("inline_disposition").ptr()[]
        )
    var v_is_noreturn: Bool = False
    if fields.ptr()[].has("is_noreturn"):
        v_is_noreturn = fields.ptr()[].get("is_noreturn").ptr()[].bool_value()
    return FunctionAttrs(v_inline_disposition^, v_is_noreturn)


def _encode_functionattrs(value: FunctionAttrs) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["inline_disposition"] = ArcPointer(JSON.string(value.inline_disposition.value()))
    fields["is_noreturn"] = ArcPointer(JSON.boolean(value.is_noreturn))
    return node("FunctionAttrs", fields^)


def _decode_opaquerecordref(value: JSON) raises -> OpaqueRecordRef:
    var fields = _fields(
        value, "OpaqueRecordRef", "|decl_id|name|c_name|is_union|size_bytes|align_bytes|"
    )
    var v_decl_id = fields.ptr()[].get("decl_id").ptr()[].text()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_c_name = fields.ptr()[].get("c_name").ptr()[].text()
    var v_is_union: Bool = False
    if fields.ptr()[].has("is_union"):
        v_is_union = fields.ptr()[].get("is_union").ptr()[].bool_value()
    var v_size_bytes: Optional[Int] = {}
    if fields.ptr()[].has("size_bytes"):
        v_size_bytes = _decode_optional_int(fields.ptr()[].get("size_bytes").ptr()[])
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    return OpaqueRecordRef(
        v_decl_id^, v_name^, v_c_name^, v_is_union, v_size_bytes^, v_align_bytes^
    )


def _encode_opaquerecordref(value: OpaqueRecordRef) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["decl_id"] = ArcPointer(JSON.string(value.decl_id.copy()))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["c_name"] = ArcPointer(JSON.string(value.c_name.copy()))
    fields["is_union"] = ArcPointer(JSON.boolean(value.is_union))
    fields["size_bytes"] = ArcPointer(_encode_optional_int(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    return node("OpaqueRecordRef", fields^)


def _decode_unsupportedtype(value: JSON) raises -> UnsupportedType:
    var fields = _fields(
        value, "UnsupportedType", "|category|spelling|reason|size_bytes|align_bytes|"
    )
    var v_category = _decode_unsupportedtypecategory(fields.ptr()[].get("category").ptr()[])
    var v_spelling = fields.ptr()[].get("spelling").ptr()[].text()
    var v_reason = fields.ptr()[].get("reason").ptr()[].text()
    var v_size_bytes: Optional[Int] = {}
    if fields.ptr()[].has("size_bytes"):
        v_size_bytes = _decode_optional_int(fields.ptr()[].get("size_bytes").ptr()[])
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    return UnsupportedType(v_category^, v_spelling^, v_reason^, v_size_bytes^, v_align_bytes^)


def _encode_unsupportedtype(value: UnsupportedType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["category"] = ArcPointer(JSON.string(value.category.value()))
    fields["spelling"] = ArcPointer(JSON.string(value.spelling.copy()))
    fields["reason"] = ArcPointer(JSON.string(value.reason.copy()))
    fields["size_bytes"] = ArcPointer(_encode_optional_int(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    return node("UnsupportedType", fields^)


def _decode_complextype(value: JSON) raises -> ComplexType:
    var fields = _fields(value, "ComplexType", "|element|size_bytes|align_bytes|")
    var v_element = _decode_floattype(fields.ptr()[].get("element").ptr()[])
    var v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    return ComplexType(v_element^, v_size_bytes, v_align_bytes^)


def _encode_complextype(value: ComplexType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["element"] = ArcPointer(_encode_floattype(value.element))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    return node("ComplexType", fields^)


def _decode_vectortype(value: JSON) raises -> VectorType:
    var fields = _fields(
        value, "VectorType", "|element|count|size_bytes|is_ext_vector|align_bytes|"
    )
    var v_element = ArcPointer(decode_c_type(fields.ptr()[].get("element").ptr()[]))
    var v_count = _decode_optional_int(fields.ptr()[].get("count").ptr()[])
    var v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_is_ext_vector: Bool = False
    if fields.ptr()[].has("is_ext_vector"):
        v_is_ext_vector = fields.ptr()[].get("is_ext_vector").ptr()[].bool_value()
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    return VectorType(v_element^, v_count^, v_size_bytes, v_is_ext_vector, v_align_bytes^)


def _encode_vectortype(value: VectorType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["element"] = ArcPointer(encode_c_type(value.element.ptr()[]))
    fields["count"] = ArcPointer(_encode_optional_int(value.count))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["is_ext_vector"] = ArcPointer(JSON.boolean(value.is_ext_vector))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    return node("VectorType", fields^)


def _decode_structref(value: JSON) raises -> StructRef:
    var fields = _fields(
        value, "StructRef", "|decl_id|name|c_name|is_union|size_bytes|align_bytes|is_anonymous|"
    )
    var v_decl_id = fields.ptr()[].get("decl_id").ptr()[].text()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_c_name = fields.ptr()[].get("c_name").ptr()[].text()
    var v_is_union: Bool = False
    if fields.ptr()[].has("is_union"):
        v_is_union = fields.ptr()[].get("is_union").ptr()[].bool_value()
    var v_size_bytes: Int = 0
    if fields.ptr()[].has("size_bytes"):
        v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("align_bytes"):
        v_align_bytes = _decode_optional_int(fields.ptr()[].get("align_bytes").ptr()[])
    var v_is_anonymous: Bool = False
    if fields.ptr()[].has("is_anonymous"):
        v_is_anonymous = fields.ptr()[].get("is_anonymous").ptr()[].bool_value()
    return StructRef(
        v_decl_id^, v_name^, v_c_name^, v_is_union, v_size_bytes, v_align_bytes^, v_is_anonymous
    )


def _encode_structref(value: StructRef) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["decl_id"] = ArcPointer(JSON.string(value.decl_id.copy()))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["c_name"] = ArcPointer(JSON.string(value.c_name.copy()))
    fields["is_union"] = ArcPointer(JSON.boolean(value.is_union))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["align_bytes"] = ArcPointer(_encode_optional_int(value.align_bytes))
    fields["is_anonymous"] = ArcPointer(JSON.boolean(value.is_anonymous))
    return node("StructRef", fields^)


def _decode_enumref(value: JSON) raises -> EnumRef:
    var fields = _fields(value, "EnumRef", "|decl_id|name|c_name|underlying|")
    var v_decl_id = fields.ptr()[].get("decl_id").ptr()[].text()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_c_name = fields.ptr()[].get("c_name").ptr()[].text()
    var v_underlying = _decode_inttype(fields.ptr()[].get("underlying").ptr()[])
    return EnumRef(v_decl_id^, v_name^, v_c_name^, v_underlying^)


def _encode_enumref(value: EnumRef) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["decl_id"] = ArcPointer(JSON.string(value.decl_id.copy()))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["c_name"] = ArcPointer(JSON.string(value.c_name.copy()))
    fields["underlying"] = ArcPointer(_encode_inttype(value.underlying))
    return node("EnumRef", fields^)


def _decode_typeref(value: JSON) raises -> TypeRef:
    var fields = _fields(value, "TypeRef", "|decl_id|name|canonical|")
    var v_decl_id = fields.ptr()[].get("decl_id").ptr()[].text()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_canonical = ArcPointer(decode_c_type(fields.ptr()[].get("canonical").ptr()[]))
    return TypeRef(v_decl_id^, v_name^, v_canonical^)


def _encode_typeref(value: TypeRef) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["decl_id"] = ArcPointer(JSON.string(value.decl_id.copy()))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["canonical"] = ArcPointer(encode_c_type(value.canonical.ptr()[]))
    return node("TypeRef", fields^)


def _decode_field(value: JSON) raises -> Field:
    var fields = _fields(
        value,
        "Field",
        "|name|source_name|type|byte_offset|size_bytes|is_anonymous|is_bitfield|bit_offset|bit_width|fam_pattern|doc|",
    )
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_source_name = fields.ptr()[].get("source_name").ptr()[].text()
    var v_type = ArcPointer(decode_c_type(fields.ptr()[].get("type").ptr()[]))
    var v_byte_offset = fields.ptr()[].get("byte_offset").ptr()[].int_value()
    var v_size_bytes: Int = 0
    if fields.ptr()[].has("size_bytes"):
        v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_is_anonymous: Bool = False
    if fields.ptr()[].has("is_anonymous"):
        v_is_anonymous = fields.ptr()[].get("is_anonymous").ptr()[].bool_value()
    var v_is_bitfield: Bool = False
    if fields.ptr()[].has("is_bitfield"):
        v_is_bitfield = fields.ptr()[].get("is_bitfield").ptr()[].bool_value()
    var v_bit_offset: Int = 0
    if fields.ptr()[].has("bit_offset"):
        v_bit_offset = fields.ptr()[].get("bit_offset").ptr()[].int_value()
    var v_bit_width: Int = 0
    if fields.ptr()[].has("bit_width"):
        v_bit_width = fields.ptr()[].get("bit_width").ptr()[].int_value()
    var v_fam_pattern: Optional[FamPattern] = {}
    if fields.ptr()[].has("fam_pattern"):
        v_fam_pattern = _decode_optional_fampattern(fields.ptr()[].get("fam_pattern").ptr()[])
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return Field(
        v_name^,
        v_source_name^,
        v_type^,
        v_byte_offset,
        v_size_bytes,
        v_is_anonymous,
        v_is_bitfield,
        v_bit_offset,
        v_bit_width,
        v_fam_pattern^,
        v_doc^,
    )


def _encode_field(value: Field) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["source_name"] = ArcPointer(JSON.string(value.source_name.copy()))
    fields["type"] = ArcPointer(encode_c_type(value.type.ptr()[]))
    fields["byte_offset"] = ArcPointer(JSON.integer(value.byte_offset))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["is_anonymous"] = ArcPointer(JSON.boolean(value.is_anonymous))
    fields["is_bitfield"] = ArcPointer(JSON.boolean(value.is_bitfield))
    fields["bit_offset"] = ArcPointer(JSON.integer(value.bit_offset))
    fields["bit_width"] = ArcPointer(JSON.integer(value.bit_width))
    fields["fam_pattern"] = ArcPointer(_encode_optional_fampattern(value.fam_pattern))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("Field", fields^)


def _decode_struct(value: JSON) raises -> Struct:
    var fields = _fields(
        value,
        "Struct",
        "|decl_id|name|c_name|fields|size_bytes|align_bytes|is_union|is_anonymous|is_complete|is_packed|requested_align_bytes|doc|",
    )
    var v_decl_id = fields.ptr()[].get("decl_id").ptr()[].text()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_c_name = fields.ptr()[].get("c_name").ptr()[].text()
    var v_fields = _decode_list_field(fields.ptr()[].get("fields").ptr()[])
    var v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_align_bytes = fields.ptr()[].get("align_bytes").ptr()[].int_value()
    var v_is_union: Bool = False
    if fields.ptr()[].has("is_union"):
        v_is_union = fields.ptr()[].get("is_union").ptr()[].bool_value()
    var v_is_anonymous: Bool = False
    if fields.ptr()[].has("is_anonymous"):
        v_is_anonymous = fields.ptr()[].get("is_anonymous").ptr()[].bool_value()
    var v_is_complete: Bool = True
    if fields.ptr()[].has("is_complete"):
        v_is_complete = fields.ptr()[].get("is_complete").ptr()[].bool_value()
    var v_is_packed: Bool = False
    if fields.ptr()[].has("is_packed"):
        v_is_packed = fields.ptr()[].get("is_packed").ptr()[].bool_value()
    var v_requested_align_bytes: Optional[Int] = {}
    if fields.ptr()[].has("requested_align_bytes"):
        v_requested_align_bytes = _decode_optional_int(
            fields.ptr()[].get("requested_align_bytes").ptr()[]
        )
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return Struct(
        v_decl_id^,
        v_name^,
        v_c_name^,
        v_fields^,
        v_size_bytes,
        v_align_bytes,
        v_is_union,
        v_is_anonymous,
        v_is_complete,
        v_is_packed,
        v_requested_align_bytes^,
        v_doc^,
    )


def _encode_struct(value: Struct) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["decl_id"] = ArcPointer(JSON.string(value.decl_id.copy()))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["c_name"] = ArcPointer(JSON.string(value.c_name.copy()))
    fields["fields"] = ArcPointer(_encode_list_field(value.fields))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["align_bytes"] = ArcPointer(JSON.integer(value.align_bytes))
    fields["is_union"] = ArcPointer(JSON.boolean(value.is_union))
    fields["is_anonymous"] = ArcPointer(JSON.boolean(value.is_anonymous))
    fields["is_complete"] = ArcPointer(JSON.boolean(value.is_complete))
    fields["is_packed"] = ArcPointer(JSON.boolean(value.is_packed))
    fields["requested_align_bytes"] = ArcPointer(_encode_optional_int(value.requested_align_bytes))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("Struct", fields^)


def _decode_intliteral(value: JSON) raises -> IntLiteral:
    var fields = _fields(value, "IntLiteral", "|value|")
    var v_value = fields.ptr()[].get("value").ptr()[].integer_value()
    return IntLiteral(v_value^)


def _encode_intliteral(value: IntLiteral) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["value"] = ArcPointer(JSON.integer(value.value.copy()))
    return node("IntLiteral", fields^)


def _decode_cfloatliteral(value: JSON) raises -> CFloatLiteral:
    var fields = _fields(value, "CFloatLiteral", "|spelling|")
    var v_spelling = fields.ptr()[].get("spelling").ptr()[].text()
    return CFloatLiteral(v_spelling^)


def _encode_cfloatliteral(value: CFloatLiteral) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["spelling"] = ArcPointer(JSON.string(value.spelling.copy()))
    return node("CFloatLiteral", fields^)


def _decode_mojofloatliteral(value: JSON) raises -> MojoFloatLiteral:
    var fields = _fields(value, "MojoFloatLiteral", "|value|")
    var v_value = fields.ptr()[].get("value").ptr()[].float_value()
    return MojoFloatLiteral(v_value)


def _encode_mojofloatliteral(value: MojoFloatLiteral) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["value"] = ArcPointer(JSON.floating(value.value))
    return node("MojoFloatLiteral", fields^)


def _decode_stringliteral(value: JSON) raises -> StringLiteral:
    var fields = _fields(value, "StringLiteral", "|value|")
    var v_value = fields.ptr()[].get("value").ptr()[].text()
    return StringLiteral(v_value^)


def _encode_stringliteral(value: StringLiteral) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["value"] = ArcPointer(JSON.string(value.value.copy()))
    return node("StringLiteral", fields^)


def _decode_charliteral(value: JSON) raises -> CharLiteral:
    var fields = _fields(value, "CharLiteral", "|value|")
    var v_value = fields.ptr()[].get("value").ptr()[].text()
    return CharLiteral(v_value^)


def _encode_charliteral(value: CharLiteral) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["value"] = ArcPointer(JSON.string(value.value.copy()))
    return node("CharLiteral", fields^)


def _decode_cnullptrliteral(value: JSON) raises -> CNullPtrLiteral:
    var fields = _fields(value, "CNullPtrLiteral", "||")
    return CNullPtrLiteral()


def _encode_cnullptrliteral(value: CNullPtrLiteral) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    return node("CNullPtrLiteral", fields^)


def _decode_crefexpr(value: JSON) raises -> CRefExpr:
    var fields = _fields(value, "CRefExpr", "|name|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    return CRefExpr(v_name^)


def _encode_crefexpr(value: CRefExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    return node("CRefExpr", fields^)


def _decode_mojorefexpr(value: JSON) raises -> MojoRefExpr:
    var fields = _fields(value, "MojoRefExpr", "|name|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    return MojoRefExpr(v_name^)


def _encode_mojorefexpr(value: MojoRefExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    return node("MojoRefExpr", fields^)


def _decode_cunaryexpr(value: JSON) raises -> CUnaryExpr:
    var fields = _fields(value, "CUnaryExpr", "|op|operand|")
    var v_op = fields.ptr()[].get("op").ptr()[].text()
    var v_operand = ArcPointer(decode_c_expr(fields.ptr()[].get("operand").ptr()[]))
    return CUnaryExpr(v_op^, v_operand^)


def _encode_cunaryexpr(value: CUnaryExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["op"] = ArcPointer(JSON.string(value.op.copy()))
    fields["operand"] = ArcPointer(encode_c_expr(value.operand.ptr()[]))
    return node("CUnaryExpr", fields^)


def _decode_mojounaryexpr(value: JSON) raises -> MojoUnaryExpr:
    var fields = _fields(value, "MojoUnaryExpr", "|op|operand|")
    var v_op = fields.ptr()[].get("op").ptr()[].text()
    var v_operand = ArcPointer(decode_mojo_expr(fields.ptr()[].get("operand").ptr()[]))
    return MojoUnaryExpr(v_op^, v_operand^)


def _encode_mojounaryexpr(value: MojoUnaryExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["op"] = ArcPointer(JSON.string(value.op.copy()))
    fields["operand"] = ArcPointer(encode_mojo_expr(value.operand.ptr()[]))
    return node("MojoUnaryExpr", fields^)


def _decode_cbinaryexpr(value: JSON) raises -> CBinaryExpr:
    var fields = _fields(value, "CBinaryExpr", "|op|lhs|rhs|")
    var v_op = fields.ptr()[].get("op").ptr()[].text()
    var v_lhs = ArcPointer(decode_c_expr(fields.ptr()[].get("lhs").ptr()[]))
    var v_rhs = ArcPointer(decode_c_expr(fields.ptr()[].get("rhs").ptr()[]))
    return CBinaryExpr(v_op^, v_lhs^, v_rhs^)


def _encode_cbinaryexpr(value: CBinaryExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["op"] = ArcPointer(JSON.string(value.op.copy()))
    fields["lhs"] = ArcPointer(encode_c_expr(value.lhs.ptr()[]))
    fields["rhs"] = ArcPointer(encode_c_expr(value.rhs.ptr()[]))
    return node("CBinaryExpr", fields^)


def _decode_mojobinaryexpr(value: JSON) raises -> MojoBinaryExpr:
    var fields = _fields(value, "MojoBinaryExpr", "|op|lhs|rhs|")
    var v_op = fields.ptr()[].get("op").ptr()[].text()
    var v_lhs = ArcPointer(decode_mojo_expr(fields.ptr()[].get("lhs").ptr()[]))
    var v_rhs = ArcPointer(decode_mojo_expr(fields.ptr()[].get("rhs").ptr()[]))
    return MojoBinaryExpr(v_op^, v_lhs^, v_rhs^)


def _encode_mojobinaryexpr(value: MojoBinaryExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["op"] = ArcPointer(JSON.string(value.op.copy()))
    fields["lhs"] = ArcPointer(encode_mojo_expr(value.lhs.ptr()[]))
    fields["rhs"] = ArcPointer(encode_mojo_expr(value.rhs.ptr()[]))
    return node("MojoBinaryExpr", fields^)


def _decode_ccastexpr(value: JSON) raises -> CCastExpr:
    var fields = _fields(value, "CCastExpr", "|target|expr|")
    var v_target = ArcPointer(decode_c_type(fields.ptr()[].get("target").ptr()[]))
    var v_expr = ArcPointer(decode_c_expr(fields.ptr()[].get("expr").ptr()[]))
    return CCastExpr(v_target^, v_expr^)


def _encode_ccastexpr(value: CCastExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["target"] = ArcPointer(encode_c_type(value.target.ptr()[]))
    fields["expr"] = ArcPointer(encode_c_expr(value.expr.ptr()[]))
    return node("CCastExpr", fields^)


def _decode_mojocastexpr(value: JSON) raises -> MojoCastExpr:
    var fields = _fields(value, "MojoCastExpr", "|target|expr|")
    var v_target = ArcPointer(decode_mojo_type(fields.ptr()[].get("target").ptr()[]))
    var v_expr = ArcPointer(decode_mojo_expr(fields.ptr()[].get("expr").ptr()[]))
    return MojoCastExpr(v_target^, v_expr^)


def _encode_mojocastexpr(value: MojoCastExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["target"] = ArcPointer(encode_mojo_type(value.target.ptr()[]))
    fields["expr"] = ArcPointer(encode_mojo_expr(value.expr.ptr()[]))
    return node("MojoCastExpr", fields^)


def _decode_csizeofexpr(value: JSON) raises -> CSizeOfExpr:
    var fields = _fields(value, "CSizeOfExpr", "|target|")
    var v_target = ArcPointer(decode_c_type(fields.ptr()[].get("target").ptr()[]))
    return CSizeOfExpr(v_target^)


def _encode_csizeofexpr(value: CSizeOfExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["target"] = ArcPointer(encode_c_type(value.target.ptr()[]))
    return node("CSizeOfExpr", fields^)


def _decode_mojosizeofexpr(value: JSON) raises -> MojoSizeOfExpr:
    var fields = _fields(value, "MojoSizeOfExpr", "|target|")
    var v_target = ArcPointer(decode_mojo_type(fields.ptr()[].get("target").ptr()[]))
    return MojoSizeOfExpr(v_target^)


def _encode_mojosizeofexpr(value: MojoSizeOfExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["target"] = ArcPointer(encode_mojo_type(value.target.ptr()[]))
    return node("MojoSizeOfExpr", fields^)


def _decode_ccallexpr(value: JSON) raises -> CCallExpr:
    var fields = _fields(value, "CCallExpr", "|callee|args|")
    var v_callee = ArcPointer(decode_c_expr(fields.ptr()[].get("callee").ptr()[]))
    var v_args: List[ArcPointer[CConstExpr]] = List[ArcPointer[CConstExpr]]()
    if fields.ptr()[].has("args"):
        v_args = _decode_list_arcpointer_cconstexpr(fields.ptr()[].get("args").ptr()[])
    return CCallExpr(v_callee^, v_args^)


def _encode_ccallexpr(value: CCallExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["callee"] = ArcPointer(encode_c_expr(value.callee.ptr()[]))
    fields["args"] = ArcPointer(_encode_list_arcpointer_cconstexpr(value.args))
    return node("CCallExpr", fields^)


def _decode_mojocallexpr(value: JSON) raises -> MojoCallExpr:
    var fields = _fields(value, "MojoCallExpr", "|callee|args|")
    var v_callee = ArcPointer(decode_mojo_expr(fields.ptr()[].get("callee").ptr()[]))
    var v_args: List[ArcPointer[MojoConstExpr]] = List[ArcPointer[MojoConstExpr]]()
    if fields.ptr()[].has("args"):
        v_args = _decode_list_arcpointer_mojoconstexpr(fields.ptr()[].get("args").ptr()[])
    return MojoCallExpr(v_callee^, v_args^)


def _encode_mojocallexpr(value: MojoCallExpr) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["callee"] = ArcPointer(encode_mojo_expr(value.callee.ptr()[]))
    fields["args"] = ArcPointer(_encode_list_arcpointer_mojoconstexpr(value.args))
    return node("MojoCallExpr", fields^)


def _decode_enumerant(value: JSON) raises -> Enumerant:
    var fields = _fields(value, "Enumerant", "|name|c_name|value|enum_decl_id|doc|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_c_name = fields.ptr()[].get("c_name").ptr()[].text()
    var v_value = fields.ptr()[].get("value").ptr()[].integer_value()
    var v_enum_decl_id: Optional[String] = {}
    if fields.ptr()[].has("enum_decl_id"):
        v_enum_decl_id = _decode_optional_string(fields.ptr()[].get("enum_decl_id").ptr()[])
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return Enumerant(v_name^, v_c_name^, v_value^, v_enum_decl_id^, v_doc^)


def _encode_enumerant(value: Enumerant) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["c_name"] = ArcPointer(JSON.string(value.c_name.copy()))
    fields["value"] = ArcPointer(JSON.integer(value.value.copy()))
    fields["enum_decl_id"] = ArcPointer(_encode_optional_string(value.enum_decl_id))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("Enumerant", fields^)


def _decode_enum(value: JSON) raises -> Enum:
    var fields = _fields(
        value, "Enum", "|decl_id|name|c_name|underlying|enumerants|alias_names|is_anonymous|doc|"
    )
    var v_decl_id = fields.ptr()[].get("decl_id").ptr()[].text()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_c_name = fields.ptr()[].get("c_name").ptr()[].text()
    var v_underlying = _decode_inttype(fields.ptr()[].get("underlying").ptr()[])
    var v_enumerants = _decode_list_enumerant(fields.ptr()[].get("enumerants").ptr()[])
    var v_alias_names: List[String] = List[String]()
    if fields.ptr()[].has("alias_names"):
        v_alias_names = _decode_list_string(fields.ptr()[].get("alias_names").ptr()[])
    var v_is_anonymous: Bool = False
    if fields.ptr()[].has("is_anonymous"):
        v_is_anonymous = fields.ptr()[].get("is_anonymous").ptr()[].bool_value()
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return Enum(
        v_decl_id^,
        v_name^,
        v_c_name^,
        v_underlying^,
        v_enumerants^,
        v_alias_names^,
        v_is_anonymous,
        v_doc^,
    )


def _encode_enum(value: Enum) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["decl_id"] = ArcPointer(JSON.string(value.decl_id.copy()))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["c_name"] = ArcPointer(JSON.string(value.c_name.copy()))
    fields["underlying"] = ArcPointer(_encode_inttype(value.underlying))
    fields["enumerants"] = ArcPointer(_encode_list_enumerant(value.enumerants))
    fields["alias_names"] = ArcPointer(_encode_list_string(value.alias_names))
    fields["is_anonymous"] = ArcPointer(JSON.boolean(value.is_anonymous))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("Enum", fields^)


def _decode_typedef(value: JSON) raises -> Typedef:
    var fields = _fields(value, "Typedef", "|decl_id|name|aliased|canonical|doc|")
    var v_decl_id = fields.ptr()[].get("decl_id").ptr()[].text()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_aliased = ArcPointer(decode_c_type(fields.ptr()[].get("aliased").ptr()[]))
    var v_canonical = ArcPointer(decode_c_type(fields.ptr()[].get("canonical").ptr()[]))
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return Typedef(v_decl_id^, v_name^, v_aliased^, v_canonical^, v_doc^)


def _encode_typedef(value: Typedef) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["decl_id"] = ArcPointer(JSON.string(value.decl_id.copy()))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["aliased"] = ArcPointer(encode_c_type(value.aliased.ptr()[]))
    fields["canonical"] = ArcPointer(encode_c_type(value.canonical.ptr()[]))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("Typedef", fields^)


def _decode_cparam(value: JSON) raises -> CParam:
    var fields = _fields(value, "CParam", "|name|type|doc|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_type = ArcPointer(decode_c_type(fields.ptr()[].get("type").ptr()[]))
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return CParam(v_name^, v_type^, v_doc^)


def _encode_cparam(value: CParam) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["type"] = ArcPointer(encode_c_type(value.type.ptr()[]))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("CParam", fields^)


def _decode_mojoparam(value: JSON) raises -> MojoParam:
    var fields = _fields(value, "MojoParam", "|name|type|doc|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_type = ArcPointer(decode_mojo_type(fields.ptr()[].get("type").ptr()[]))
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return MojoParam(v_name^, v_type^, v_doc^)


def _encode_mojoparam(value: MojoParam) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["type"] = ArcPointer(encode_mojo_type(value.type.ptr()[]))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("MojoParam", fields^)


def _decode_function(value: JSON) raises -> Function:
    var fields = _fields(
        value,
        "Function",
        "|name|link_name|ret|params|is_variadic|decl_id|calling_convention|attrs|doc|",
    )
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_link_name = fields.ptr()[].get("link_name").ptr()[].text()
    var v_ret = ArcPointer(decode_c_type(fields.ptr()[].get("ret").ptr()[]))
    var v_params = _decode_list_cparam(fields.ptr()[].get("params").ptr()[])
    var v_is_variadic: Bool = False
    if fields.ptr()[].has("is_variadic"):
        v_is_variadic = fields.ptr()[].get("is_variadic").ptr()[].bool_value()
    var v_decl_id: String = ""
    if fields.ptr()[].has("decl_id"):
        v_decl_id = fields.ptr()[].get("decl_id").ptr()[].text()
    var v_calling_convention: Optional[String] = {}
    if fields.ptr()[].has("calling_convention"):
        v_calling_convention = _decode_optional_string(
            fields.ptr()[].get("calling_convention").ptr()[]
        )
    var v_attrs: FunctionAttrs = FunctionAttrs()
    if fields.ptr()[].has("attrs"):
        v_attrs = _decode_functionattrs(fields.ptr()[].get("attrs").ptr()[])
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return Function(
        v_name^,
        v_link_name^,
        v_ret^,
        v_params^,
        v_is_variadic,
        v_decl_id^,
        v_calling_convention^,
        v_attrs^,
        v_doc^,
    )


def _encode_function(value: Function) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["link_name"] = ArcPointer(JSON.string(value.link_name.copy()))
    fields["ret"] = ArcPointer(encode_c_type(value.ret.ptr()[]))
    fields["params"] = ArcPointer(_encode_list_cparam(value.params))
    fields["is_variadic"] = ArcPointer(JSON.boolean(value.is_variadic))
    fields["decl_id"] = ArcPointer(JSON.string(value.decl_id.copy()))
    fields["calling_convention"] = ArcPointer(_encode_optional_string(value.calling_convention))
    fields["attrs"] = ArcPointer(_encode_functionattrs(value.attrs))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("Function", fields^)


def _decode_const(value: JSON) raises -> Const:
    var fields = _fields(value, "Const", "|name|type|expr|doc|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_type = ArcPointer(decode_c_type(fields.ptr()[].get("type").ptr()[]))
    var v_expr = ArcPointer(decode_c_expr(fields.ptr()[].get("expr").ptr()[]))
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return Const(v_name^, v_type^, v_expr^, v_doc^)


def _encode_const(value: Const) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["type"] = ArcPointer(encode_c_type(value.type.ptr()[]))
    fields["expr"] = ArcPointer(encode_c_expr(value.expr.ptr()[]))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("Const", fields^)


def _decode_macrodecl(value: JSON) raises -> MacroDecl:
    var fields = _fields(value, "MacroDecl", "|name|tokens|kind|expr|type|diagnostic|doc|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_tokens = _decode_list_string(fields.ptr()[].get("tokens").ptr()[])
    var v_kind = _decode_macrodeclkind(fields.ptr()[].get("kind").ptr()[])
    var v_expr: Optional[ArcPointer[CConstExpr]] = {}
    if fields.ptr()[].has("expr"):
        v_expr = _decode_optional_arcpointer_cconstexpr(fields.ptr()[].get("expr").ptr()[])
    var v_type: Optional[ArcPointer[CType]] = {}
    if fields.ptr()[].has("type"):
        v_type = _decode_optional_arcpointer_ctype(fields.ptr()[].get("type").ptr()[])
    var v_diagnostic: Optional[String] = {}
    if fields.ptr()[].has("diagnostic"):
        v_diagnostic = _decode_optional_string(fields.ptr()[].get("diagnostic").ptr()[])
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return MacroDecl(v_name^, v_tokens^, v_kind^, v_expr^, v_type^, v_diagnostic^, v_doc^)


def _encode_macrodecl(value: MacroDecl) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["tokens"] = ArcPointer(_encode_list_string(value.tokens))
    fields["kind"] = ArcPointer(JSON.string(value.kind.value()))
    fields["expr"] = ArcPointer(_encode_optional_arcpointer_cconstexpr(value.expr))
    fields["type"] = ArcPointer(_encode_optional_arcpointer_ctype(value.type))
    fields["diagnostic"] = ArcPointer(_encode_optional_string(value.diagnostic))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("MacroDecl", fields^)


def _decode_globalvar(value: JSON) raises -> GlobalVar:
    var fields = _fields(
        value, "GlobalVar", "|decl_id|name|link_name|type|is_const|initializer|doc|"
    )
    var v_decl_id = fields.ptr()[].get("decl_id").ptr()[].text()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_link_name = fields.ptr()[].get("link_name").ptr()[].text()
    var v_type = ArcPointer(decode_c_type(fields.ptr()[].get("type").ptr()[]))
    var v_is_const: Bool = False
    if fields.ptr()[].has("is_const"):
        v_is_const = fields.ptr()[].get("is_const").ptr()[].bool_value()
    var v_initializer: Optional[ArcPointer[CConstExpr]] = {}
    if fields.ptr()[].has("initializer"):
        v_initializer = _decode_optional_arcpointer_cconstexpr(
            fields.ptr()[].get("initializer").ptr()[]
        )
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return GlobalVar(v_decl_id^, v_name^, v_link_name^, v_type^, v_is_const, v_initializer^, v_doc^)


def _encode_globalvar(value: GlobalVar) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["decl_id"] = ArcPointer(JSON.string(value.decl_id.copy()))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["link_name"] = ArcPointer(JSON.string(value.link_name.copy()))
    fields["type"] = ArcPointer(encode_c_type(value.type.ptr()[]))
    fields["is_const"] = ArcPointer(JSON.boolean(value.is_const))
    fields["initializer"] = ArcPointer(_encode_optional_arcpointer_cconstexpr(value.initializer))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("GlobalVar", fields^)


def _decode_irdiagnostic(value: JSON) raises -> IRDiagnostic:
    var fields = _fields(value, "IRDiagnostic", "|severity|message|file|line|col|decl_id|")
    var v_severity = fields.ptr()[].get("severity").ptr()[].text()
    var v_message = fields.ptr()[].get("message").ptr()[].text()
    var v_file: Optional[String] = {}
    if fields.ptr()[].has("file"):
        v_file = _decode_optional_string(fields.ptr()[].get("file").ptr()[])
    var v_line: Optional[Int] = {}
    if fields.ptr()[].has("line"):
        v_line = _decode_optional_int(fields.ptr()[].get("line").ptr()[])
    var v_col: Optional[Int] = {}
    if fields.ptr()[].has("col"):
        v_col = _decode_optional_int(fields.ptr()[].get("col").ptr()[])
    var v_decl_id: Optional[String] = {}
    if fields.ptr()[].has("decl_id"):
        v_decl_id = _decode_optional_string(fields.ptr()[].get("decl_id").ptr()[])
    return IRDiagnostic(v_severity^, v_message^, v_file^, v_line^, v_col^, v_decl_id^)


def _encode_irdiagnostic(value: IRDiagnostic) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["severity"] = ArcPointer(JSON.string(value.severity.copy()))
    fields["message"] = ArcPointer(JSON.string(value.message.copy()))
    fields["file"] = ArcPointer(_encode_optional_string(value.file))
    fields["line"] = ArcPointer(_encode_optional_int(value.line))
    fields["col"] = ArcPointer(_encode_optional_int(value.col))
    fields["decl_id"] = ArcPointer(_encode_optional_string(value.decl_id))
    return node("IRDiagnostic", fields^)


def _decode_targetabi(value: JSON) raises -> TargetABI:
    var fields = _fields(
        value, "TargetABI", "|pointer_size_bytes|pointer_align_bytes|byte_order|target_triple|"
    )
    var v_pointer_size_bytes = fields.ptr()[].get("pointer_size_bytes").ptr()[].int_value()
    var v_pointer_align_bytes = fields.ptr()[].get("pointer_align_bytes").ptr()[].int_value()
    var v_byte_order = _decode_byteorder(fields.ptr()[].get("byte_order").ptr()[])
    var v_target_triple: Optional[String] = {}
    if fields.ptr()[].has("target_triple"):
        v_target_triple = _decode_optional_string(fields.ptr()[].get("target_triple").ptr()[])
    return TargetABI(v_pointer_size_bytes, v_pointer_align_bytes, v_byte_order^, v_target_triple^)


def _encode_targetabi(value: TargetABI) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["pointer_size_bytes"] = ArcPointer(JSON.integer(value.pointer_size_bytes))
    fields["pointer_align_bytes"] = ArcPointer(JSON.integer(value.pointer_align_bytes))
    fields["byte_order"] = ArcPointer(JSON.string(value.byte_order.value()))
    fields["target_triple"] = ArcPointer(_encode_optional_string(value.target_triple))
    return node("TargetABI", fields^)


def _decode_unit(value: JSON) raises -> Unit:
    var fields = _fields(
        value, "Unit", "|source_header|library|link_name|target_abi|decls|diagnostics|"
    )
    var v_source_header = fields.ptr()[].get("source_header").ptr()[].text()
    var v_library = fields.ptr()[].get("library").ptr()[].text()
    var v_link_name = fields.ptr()[].get("link_name").ptr()[].text()
    var v_target_abi = _decode_targetabi(fields.ptr()[].get("target_abi").ptr()[])
    var v_decls: List[Decl] = List[Decl]()
    if fields.ptr()[].has("decls"):
        v_decls = _decode_list_decl(fields.ptr()[].get("decls").ptr()[])
    var v_diagnostics: List[IRDiagnostic] = List[IRDiagnostic]()
    if fields.ptr()[].has("diagnostics"):
        v_diagnostics = _decode_list_irdiagnostic(fields.ptr()[].get("diagnostics").ptr()[])
    return Unit(v_source_header^, v_library^, v_link_name^, v_target_abi^, v_decls^, v_diagnostics^)


def _encode_unit(value: Unit) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["source_header"] = ArcPointer(JSON.string(value.source_header.copy()))
    fields["library"] = ArcPointer(JSON.string(value.library.copy()))
    fields["link_name"] = ArcPointer(JSON.string(value.link_name.copy()))
    fields["target_abi"] = ArcPointer(_encode_targetabi(value.target_abi))
    fields["decls"] = ArcPointer(_encode_list_decl(value.decls))
    fields["diagnostics"] = ArcPointer(_encode_list_irdiagnostic(value.diagnostics))
    return node("Unit", fields^)


def _decode_primitivedtype(value: JSON) raises -> PrimitiveDType:
    var fields = _fields(value, "PrimitiveDType", "|kind|signed|dtype|width_bytes|")
    var v_kind = _decode_primitivekind(fields.ptr()[].get("kind").ptr()[])
    var v_signed = fields.ptr()[].get("signed").ptr()[].bool_value()
    var v_dtype = fields.ptr()[].get("dtype").ptr()[].text()
    var v_width_bytes = fields.ptr()[].get("width_bytes").ptr()[].int_value()
    return PrimitiveDType(v_kind^, v_signed, v_dtype^, v_width_bytes)


def _encode_primitivedtype(value: PrimitiveDType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["kind"] = ArcPointer(JSON.string(value.kind.value()))
    fields["signed"] = ArcPointer(JSON.boolean(value.signed))
    fields["dtype"] = ArcPointer(JSON.string(value.dtype.copy()))
    fields["width_bytes"] = ArcPointer(JSON.integer(value.width_bytes))
    return node("PrimitiveDType", fields^)


def _decode_mappingnote(value: JSON) raises -> MappingNote:
    var fields = _fields(value, "MappingNote", "|severity|message|category|")
    var v_severity = _decode_mappingseverity(fields.ptr()[].get("severity").ptr()[])
    var v_message = fields.ptr()[].get("message").ptr()[].text()
    var v_category = fields.ptr()[].get("category").ptr()[].text()
    return MappingNote(v_severity^, v_message^, v_category^)


def _encode_mappingnote(value: MappingNote) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["severity"] = ArcPointer(JSON.string(value.severity.value()))
    fields["message"] = ArcPointer(JSON.string(value.message.copy()))
    fields["category"] = ArcPointer(JSON.string(value.category.copy()))
    return node("MappingNote", fields^)


def _decode_moduleimport(value: JSON) raises -> ModuleImport:
    var fields = _fields(value, "ModuleImport", "|module|names|")
    var v_module = fields.ptr()[].get("module").ptr()[].text()
    var v_names = _decode_list_string(fields.ptr()[].get("names").ptr()[])
    return ModuleImport(v_module^, v_names^)


def _encode_moduleimport(value: ModuleImport) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["module"] = ArcPointer(JSON.string(value.module.copy()))
    fields["names"] = ArcPointer(_encode_list_string(value.names))
    return node("ModuleImport", fields^)


def _decode_supportdecl(value: JSON) raises -> SupportDecl:
    var fields = _fields(value, "SupportDecl", "|kind|")
    var v_kind = _decode_supportdeclkind(fields.ptr()[].get("kind").ptr()[])
    return SupportDecl(v_kind^)


def _encode_supportdecl(value: SupportDecl) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["kind"] = ArcPointer(JSON.string(value.kind.value()))
    return node("SupportDecl", fields^)


def _decode_moduledependencies(value: JSON) raises -> ModuleDependencies:
    var fields = _fields(value, "ModuleDependencies", "|imports|support_decls|")
    var v_imports: List[ModuleImport] = List[ModuleImport]()
    if fields.ptr()[].has("imports"):
        v_imports = _decode_list_moduleimport(fields.ptr()[].get("imports").ptr()[])
    var v_support_decls: List[SupportDecl] = List[SupportDecl]()
    if fields.ptr()[].has("support_decls"):
        v_support_decls = _decode_list_supportdecl(fields.ptr()[].get("support_decls").ptr()[])
    return ModuleDependencies(v_imports^, v_support_decls^)


def _encode_moduledependencies(value: ModuleDependencies) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["imports"] = ArcPointer(_encode_list_moduleimport(value.imports))
    fields["support_decls"] = ArcPointer(_encode_list_supportdecl(value.support_decls))
    return node("ModuleDependencies", fields^)


def _decode_builtintype(value: JSON) raises -> BuiltinType:
    var fields = _fields(value, "BuiltinType", "|name|")
    var v_name = _decode_mojobuiltin(fields.ptr()[].get("name").ptr()[])
    return BuiltinType(v_name^)


def _encode_builtintype(value: BuiltinType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.value()))
    return node("BuiltinType", fields^)


def _decode_namedtype(value: JSON) raises -> NamedType:
    var fields = _fields(value, "NamedType", "|name|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    return NamedType(v_name^)


def _encode_namedtype(value: NamedType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    return node("NamedType", fields^)


def _decode_dtypearg(value: JSON) raises -> DTypeArg:
    var fields = _fields(value, "DTypeArg", "|value|")
    var v_value = fields.ptr()[].get("value").ptr()[].text()
    return DTypeArg(v_value^)


def _encode_dtypearg(value: DTypeArg) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["value"] = ArcPointer(JSON.string(value.value.copy()))
    return node("DTypeArg", fields^)


def _decode_constarg(value: JSON) raises -> ConstArg:
    var fields = _fields(value, "ConstArg", "|value|")
    var v_value = fields.ptr()[].get("value").ptr()[].integer_value()
    return ConstArg(v_value^)


def _encode_constarg(value: ConstArg) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["value"] = ArcPointer(JSON.integer(value.value.copy()))
    return node("ConstArg", fields^)


def _decode_namearg(value: JSON) raises -> NameArg:
    var fields = _fields(value, "NameArg", "|value|")
    var v_value = fields.ptr()[].get("value").ptr()[].text()
    return NameArg(v_value^)


def _encode_namearg(value: NameArg) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["value"] = ArcPointer(JSON.string(value.value.copy()))
    return node("NameArg", fields^)


def _decode_typearg(value: JSON) raises -> TypeArg:
    var fields = _fields(value, "TypeArg", "|type|")
    var v_type = ArcPointer(decode_mojo_type(fields.ptr()[].get("type").ptr()[]))
    return TypeArg(v_type^)


def _encode_typearg(value: TypeArg) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["type"] = ArcPointer(encode_mojo_type(value.type.ptr()[]))
    return node("TypeArg", fields^)


def _decode_parametrictype(value: JSON) raises -> ParametricType:
    var fields = _fields(value, "ParametricType", "|base|args|")
    var v_base = _decode_parametricbase(fields.ptr()[].get("base").ptr()[])
    var v_args: List[ParametricArg] = List[ParametricArg]()
    if fields.ptr()[].has("args"):
        v_args = _decode_list_parametricarg(fields.ptr()[].get("args").ptr()[])
    return ParametricType(v_base^, v_args^)


def _encode_parametrictype(value: ParametricType) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["base"] = ArcPointer(JSON.string(value.base.value()))
    fields["args"] = ArcPointer(_encode_list_parametricarg(value.args))
    return node("ParametricType", fields^)


def _decode_storedmember(value: JSON) raises -> StoredMember:
    var fields = _fields(value, "StoredMember", "|index|name|type|byte_offset|doc|")
    var v_index = fields.ptr()[].get("index").ptr()[].int_value()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_type = ArcPointer(decode_mojo_type(fields.ptr()[].get("type").ptr()[]))
    var v_byte_offset = fields.ptr()[].get("byte_offset").ptr()[].int_value()
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return StoredMember(v_index, v_name^, v_type^, v_byte_offset, v_doc^)


def _encode_storedmember(value: StoredMember) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["index"] = ArcPointer(JSON.integer(value.index))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["type"] = ArcPointer(encode_mojo_type(value.type.ptr()[]))
    fields["byte_offset"] = ArcPointer(JSON.integer(value.byte_offset))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("StoredMember", fields^)


def _decode_paddingmember(value: JSON) raises -> PaddingMember:
    var fields = _fields(value, "PaddingMember", "|name|size_bytes|byte_offset|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    var v_byte_offset = fields.ptr()[].get("byte_offset").ptr()[].int_value()
    return PaddingMember(v_name^, v_size_bytes, v_byte_offset)


def _encode_paddingmember(value: PaddingMember) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    fields["byte_offset"] = ArcPointer(JSON.integer(value.byte_offset))
    return node("PaddingMember", fields^)


def _decode_opaquestoragemember(value: JSON) raises -> OpaqueStorageMember:
    var fields = _fields(value, "OpaqueStorageMember", "|name|size_bytes|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_size_bytes = fields.ptr()[].get("size_bytes").ptr()[].int_value()
    return OpaqueStorageMember(v_name^, v_size_bytes)


def _encode_opaquestoragemember(value: OpaqueStorageMember) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["size_bytes"] = ArcPointer(JSON.integer(value.size_bytes))
    return node("OpaqueStorageMember", fields^)


def _decode_bitfieldfield(value: JSON) raises -> BitfieldField:
    var fields = _fields(
        value,
        "BitfieldField",
        "|index|name|logical_type|bit_offset|bit_width|signed|bool_semantics|doc|",
    )
    var v_index = fields.ptr()[].get("index").ptr()[].int_value()
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_logical_type = ArcPointer(decode_mojo_type(fields.ptr()[].get("logical_type").ptr()[]))
    var v_bit_offset = fields.ptr()[].get("bit_offset").ptr()[].int_value()
    var v_bit_width = fields.ptr()[].get("bit_width").ptr()[].int_value()
    var v_signed = fields.ptr()[].get("signed").ptr()[].bool_value()
    var v_bool_semantics: Bool = False
    if fields.ptr()[].has("bool_semantics"):
        v_bool_semantics = fields.ptr()[].get("bool_semantics").ptr()[].bool_value()
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return BitfieldField(
        v_index,
        v_name^,
        v_logical_type^,
        v_bit_offset,
        v_bit_width,
        v_signed,
        v_bool_semantics,
        v_doc^,
    )


def _encode_bitfieldfield(value: BitfieldField) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["index"] = ArcPointer(JSON.integer(value.index))
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["logical_type"] = ArcPointer(encode_mojo_type(value.logical_type.ptr()[]))
    fields["bit_offset"] = ArcPointer(JSON.integer(value.bit_offset))
    fields["bit_width"] = ArcPointer(JSON.integer(value.bit_width))
    fields["signed"] = ArcPointer(JSON.boolean(value.signed))
    fields["bool_semantics"] = ArcPointer(JSON.boolean(value.bool_semantics))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("BitfieldField", fields^)


def _decode_bitfieldgroupmember(value: JSON) raises -> BitfieldGroupMember:
    var fields = _fields(
        value,
        "BitfieldGroupMember",
        "|storage_name|storage_type|byte_offset|first_index|storage_width_bits|fields|",
    )
    var v_storage_name = fields.ptr()[].get("storage_name").ptr()[].text()
    var v_storage_type = ArcPointer(decode_mojo_type(fields.ptr()[].get("storage_type").ptr()[]))
    var v_byte_offset = fields.ptr()[].get("byte_offset").ptr()[].int_value()
    var v_first_index = fields.ptr()[].get("first_index").ptr()[].int_value()
    var v_storage_width_bits = fields.ptr()[].get("storage_width_bits").ptr()[].int_value()
    var v_fields: List[BitfieldField] = List[BitfieldField]()
    if fields.ptr()[].has("fields"):
        v_fields = _decode_list_bitfieldfield(fields.ptr()[].get("fields").ptr()[])
    return BitfieldGroupMember(
        v_storage_name^,
        v_storage_type^,
        v_byte_offset,
        v_first_index,
        v_storage_width_bits,
        v_fields^,
    )


def _encode_bitfieldgroupmember(value: BitfieldGroupMember) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["storage_name"] = ArcPointer(JSON.string(value.storage_name.copy()))
    fields["storage_type"] = ArcPointer(encode_mojo_type(value.storage_type.ptr()[]))
    fields["byte_offset"] = ArcPointer(JSON.integer(value.byte_offset))
    fields["first_index"] = ArcPointer(JSON.integer(value.first_index))
    fields["storage_width_bits"] = ArcPointer(JSON.integer(value.storage_width_bits))
    fields["fields"] = ArcPointer(_encode_list_bitfieldfield(value.fields))
    return node("BitfieldGroupMember", fields^)


def _decode_comptimemember(value: JSON) raises -> ComptimeMember:
    var fields = _fields(value, "ComptimeMember", "|name|type_value|const_value|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_type_value: Optional[ArcPointer[MojoType]] = {}
    if fields.ptr()[].has("type_value"):
        v_type_value = _decode_optional_arcpointer_mojotype(
            fields.ptr()[].get("type_value").ptr()[]
        )
    var v_const_value: Optional[ArcPointer[MojoConstExpr]] = {}
    if fields.ptr()[].has("const_value"):
        v_const_value = _decode_optional_arcpointer_mojoconstexpr(
            fields.ptr()[].get("const_value").ptr()[]
        )
    return ComptimeMember(v_name^, v_type_value^, v_const_value^)


def _encode_comptimemember(value: ComptimeMember) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["type_value"] = ArcPointer(_encode_optional_arcpointer_mojotype(value.type_value))
    fields["const_value"] = ArcPointer(_encode_optional_arcpointer_mojoconstexpr(value.const_value))
    return node("ComptimeMember", fields^)


def _decode_initializerparam(value: JSON) raises -> InitializerParam:
    var fields = _fields(value, "InitializerParam", "|name|type|")
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_type = ArcPointer(decode_mojo_type(fields.ptr()[].get("type").ptr()[]))
    return InitializerParam(v_name^, v_type^)


def _encode_initializerparam(value: InitializerParam) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["type"] = ArcPointer(encode_mojo_type(value.type.ptr()[]))
    return node("InitializerParam", fields^)


def _decode_initializer(value: JSON) raises -> Initializer:
    var fields = _fields(value, "Initializer", "|params|")
    var v_params: List[InitializerParam] = List[InitializerParam]()
    if fields.ptr()[].has("params"):
        v_params = _decode_list_initializerparam(fields.ptr()[].get("params").ptr()[])
    return Initializer(v_params^)


def _encode_initializer(value: Initializer) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["params"] = ArcPointer(_encode_list_initializerparam(value.params))
    return node("Initializer", fields^)


def _decode_flexibletail(value: JSON) raises -> FlexibleTail:
    var fields = _fields(value, "FlexibleTail", "|field_name|element_type|pattern|byte_offset|")
    var v_field_name = fields.ptr()[].get("field_name").ptr()[].text()
    var v_element_type = ArcPointer(decode_mojo_type(fields.ptr()[].get("element_type").ptr()[]))
    var v_pattern = fields.ptr()[].get("pattern").ptr()[].text()
    var v_byte_offset = fields.ptr()[].get("byte_offset").ptr()[].int_value()
    return FlexibleTail(v_field_name^, v_element_type^, v_pattern^, v_byte_offset)


def _encode_flexibletail(value: FlexibleTail) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["field_name"] = ArcPointer(JSON.string(value.field_name.copy()))
    fields["element_type"] = ArcPointer(encode_mojo_type(value.element_type.ptr()[]))
    fields["pattern"] = ArcPointer(JSON.string(value.pattern.copy()))
    fields["byte_offset"] = ArcPointer(JSON.integer(value.byte_offset))
    return node("FlexibleTail", fields^)


def _decode_structdecl(value: JSON) raises -> StructDecl:
    var fields = _fields(
        value,
        "StructDecl",
        "|name|traits|passability|align|align_decorator|fieldwise_init|kind|members|comptime_members|initializers|flexible_tail|diagnostics|doc|",
    )
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_traits: List[StructTraits] = List[StructTraits]()
    if fields.ptr()[].has("traits"):
        v_traits = _decode_list_structtraits(fields.ptr()[].get("traits").ptr()[])
    var v_passability: MojoPassability = MojoPassability.MEMORY_ONLY
    if fields.ptr()[].has("passability"):
        v_passability = _decode_mojopassability(fields.ptr()[].get("passability").ptr()[])
    var v_align: Optional[Int] = {}
    if fields.ptr()[].has("align"):
        v_align = _decode_optional_int(fields.ptr()[].get("align").ptr()[])
    var v_align_decorator: Optional[Int] = {}
    if fields.ptr()[].has("align_decorator"):
        v_align_decorator = _decode_optional_int(fields.ptr()[].get("align_decorator").ptr()[])
    var v_fieldwise_init: Bool = False
    if fields.ptr()[].has("fieldwise_init"):
        v_fieldwise_init = fields.ptr()[].get("fieldwise_init").ptr()[].bool_value()
    var v_kind: StructKind = StructKind.PLAIN
    if fields.ptr()[].has("kind"):
        v_kind = _decode_structkind(fields.ptr()[].get("kind").ptr()[])
    var v_members: List[StructMember] = List[StructMember]()
    if fields.ptr()[].has("members"):
        v_members = _decode_list_structmember(fields.ptr()[].get("members").ptr()[])
    var v_comptime_members: List[ComptimeMember] = List[ComptimeMember]()
    if fields.ptr()[].has("comptime_members"):
        v_comptime_members = _decode_list_comptimemember(
            fields.ptr()[].get("comptime_members").ptr()[]
        )
    var v_initializers: List[Initializer] = List[Initializer]()
    if fields.ptr()[].has("initializers"):
        v_initializers = _decode_list_initializer(fields.ptr()[].get("initializers").ptr()[])
    var v_flexible_tail: Optional[FlexibleTail] = {}
    if fields.ptr()[].has("flexible_tail"):
        v_flexible_tail = _decode_optional_flexibletail(fields.ptr()[].get("flexible_tail").ptr()[])
    var v_diagnostics: List[MappingNote] = List[MappingNote]()
    if fields.ptr()[].has("diagnostics"):
        v_diagnostics = _decode_list_mappingnote(fields.ptr()[].get("diagnostics").ptr()[])
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return StructDecl(
        v_name^,
        v_traits^,
        v_passability^,
        v_align^,
        v_align_decorator^,
        v_fieldwise_init,
        v_kind^,
        v_members^,
        v_comptime_members^,
        v_initializers^,
        v_flexible_tail^,
        v_diagnostics^,
        v_doc^,
    )


def _encode_structdecl(value: StructDecl) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["traits"] = ArcPointer(_encode_list_structtraits(value.traits))
    fields["passability"] = ArcPointer(JSON.string(value.passability.value()))
    fields["align"] = ArcPointer(_encode_optional_int(value.align))
    fields["align_decorator"] = ArcPointer(_encode_optional_int(value.align_decorator))
    fields["fieldwise_init"] = ArcPointer(JSON.boolean(value.fieldwise_init))
    fields["kind"] = ArcPointer(JSON.string(value.kind.value()))
    fields["members"] = ArcPointer(_encode_list_structmember(value.members))
    fields["comptime_members"] = ArcPointer(_encode_list_comptimemember(value.comptime_members))
    fields["initializers"] = ArcPointer(_encode_list_initializer(value.initializers))
    fields["flexible_tail"] = ArcPointer(_encode_optional_flexibletail(value.flexible_tail))
    fields["diagnostics"] = ArcPointer(_encode_list_mappingnote(value.diagnostics))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("StructDecl", fields^)


def _decode_aliasdecl(value: JSON) raises -> AliasDecl:
    var fields = _fields(
        value, "AliasDecl", "|name|kind|type_value|const_type|const_value|diagnostics|doc|"
    )
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_kind = _decode_aliaskind(fields.ptr()[].get("kind").ptr()[])
    var v_type_value: Optional[ArcPointer[MojoType]] = {}
    if fields.ptr()[].has("type_value"):
        v_type_value = _decode_optional_arcpointer_mojotype(
            fields.ptr()[].get("type_value").ptr()[]
        )
    var v_const_type: Optional[ArcPointer[MojoType]] = {}
    if fields.ptr()[].has("const_type"):
        v_const_type = _decode_optional_arcpointer_mojotype(
            fields.ptr()[].get("const_type").ptr()[]
        )
    var v_const_value: Optional[ArcPointer[MojoConstExpr]] = {}
    if fields.ptr()[].has("const_value"):
        v_const_value = _decode_optional_arcpointer_mojoconstexpr(
            fields.ptr()[].get("const_value").ptr()[]
        )
    var v_diagnostics: List[MappingNote] = List[MappingNote]()
    if fields.ptr()[].has("diagnostics"):
        v_diagnostics = _decode_list_mappingnote(fields.ptr()[].get("diagnostics").ptr()[])
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return AliasDecl(
        v_name^, v_kind^, v_type_value^, v_const_type^, v_const_value^, v_diagnostics^, v_doc^
    )


def _encode_aliasdecl(value: AliasDecl) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["kind"] = ArcPointer(JSON.string(value.kind.value()))
    fields["type_value"] = ArcPointer(_encode_optional_arcpointer_mojotype(value.type_value))
    fields["const_type"] = ArcPointer(_encode_optional_arcpointer_mojotype(value.const_type))
    fields["const_value"] = ArcPointer(_encode_optional_arcpointer_mojoconstexpr(value.const_value))
    fields["diagnostics"] = ArcPointer(_encode_list_mappingnote(value.diagnostics))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("AliasDecl", fields^)


def _decode_calltarget(value: JSON) raises -> CallTarget:
    var fields = _fields(value, "CallTarget", "|link_mode|symbol|")
    var v_link_mode = _decode_linkmode(fields.ptr()[].get("link_mode").ptr()[])
    var v_symbol = fields.ptr()[].get("symbol").ptr()[].text()
    return CallTarget(v_link_mode^, v_symbol^)


def _encode_calltarget(value: CallTarget) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["link_mode"] = ArcPointer(JSON.string(value.link_mode.value()))
    fields["symbol"] = ArcPointer(JSON.string(value.symbol.copy()))
    return node("CallTarget", fields^)


def _decode_functiondecl(value: JSON) raises -> FunctionDecl:
    var fields = _fields(
        value,
        "FunctionDecl",
        "|name|link_name|params|return_type|kind|call_target|attrs|num_fixed_args|diagnostics|doc|",
    )
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_link_name = fields.ptr()[].get("link_name").ptr()[].text()
    var v_params: List[MojoParam] = List[MojoParam]()
    if fields.ptr()[].has("params"):
        v_params = _decode_list_mojoparam(fields.ptr()[].get("params").ptr()[])
    var v_return_type: ArcPointer[MojoType] = ArcPointer(
        MojoType.builtin_type(BuiltinType(MojoBuiltin.NONE))
    )
    if fields.ptr()[].has("return_type"):
        v_return_type = ArcPointer(decode_mojo_type(fields.ptr()[].get("return_type").ptr()[]))
    var v_kind: FunctionKind = FunctionKind.WRAPPER
    if fields.ptr()[].has("kind"):
        v_kind = _decode_functionkind(fields.ptr()[].get("kind").ptr()[])
    var v_call_target: CallTarget = CallTarget(LinkMode.EXTERNAL_CALL, "")
    if fields.ptr()[].has("call_target"):
        v_call_target = _decode_calltarget(fields.ptr()[].get("call_target").ptr()[])
    var v_attrs: FunctionAttrs = FunctionAttrs()
    if fields.ptr()[].has("attrs"):
        v_attrs = _decode_functionattrs(fields.ptr()[].get("attrs").ptr()[])
    var v_num_fixed_args: Optional[Int] = {}
    if fields.ptr()[].has("num_fixed_args"):
        v_num_fixed_args = _decode_optional_int(fields.ptr()[].get("num_fixed_args").ptr()[])
    var v_diagnostics: List[MappingNote] = List[MappingNote]()
    if fields.ptr()[].has("diagnostics"):
        v_diagnostics = _decode_list_mappingnote(fields.ptr()[].get("diagnostics").ptr()[])
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return FunctionDecl(
        v_name^,
        v_link_name^,
        v_params^,
        v_return_type^,
        v_kind^,
        v_call_target^,
        v_attrs^,
        v_num_fixed_args^,
        v_diagnostics^,
        v_doc^,
    )


def _encode_functiondecl(value: FunctionDecl) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["link_name"] = ArcPointer(JSON.string(value.link_name.copy()))
    fields["params"] = ArcPointer(_encode_list_mojoparam(value.params))
    fields["return_type"] = ArcPointer(encode_mojo_type(value.return_type.ptr()[]))
    fields["kind"] = ArcPointer(JSON.string(value.kind.value()))
    fields["call_target"] = ArcPointer(_encode_calltarget(value.call_target))
    fields["attrs"] = ArcPointer(_encode_functionattrs(value.attrs))
    fields["num_fixed_args"] = ArcPointer(_encode_optional_int(value.num_fixed_args))
    fields["diagnostics"] = ArcPointer(_encode_list_mappingnote(value.diagnostics))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("FunctionDecl", fields^)


def _decode_globaldecl(value: JSON) raises -> GlobalDecl:
    var fields = _fields(
        value, "GlobalDecl", "|name|link_name|value_type|is_const|kind|diagnostics|doc|"
    )
    var v_name = fields.ptr()[].get("name").ptr()[].text()
    var v_link_name = fields.ptr()[].get("link_name").ptr()[].text()
    var v_value_type = ArcPointer(decode_mojo_type(fields.ptr()[].get("value_type").ptr()[]))
    var v_is_const: Bool = False
    if fields.ptr()[].has("is_const"):
        v_is_const = fields.ptr()[].get("is_const").ptr()[].bool_value()
    var v_kind: GlobalKind = GlobalKind.WRAPPER
    if fields.ptr()[].has("kind"):
        v_kind = _decode_globalkind(fields.ptr()[].get("kind").ptr()[])
    var v_diagnostics: List[MappingNote] = List[MappingNote]()
    if fields.ptr()[].has("diagnostics"):
        v_diagnostics = _decode_list_mappingnote(fields.ptr()[].get("diagnostics").ptr()[])
    var v_doc: Optional[DocComment] = {}
    if fields.ptr()[].has("doc"):
        v_doc = _decode_optional_doccomment(fields.ptr()[].get("doc").ptr()[])
    return GlobalDecl(
        v_name^, v_link_name^, v_value_type^, v_is_const, v_kind^, v_diagnostics^, v_doc^
    )


def _encode_globaldecl(value: GlobalDecl) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["name"] = ArcPointer(JSON.string(value.name.copy()))
    fields["link_name"] = ArcPointer(JSON.string(value.link_name.copy()))
    fields["value_type"] = ArcPointer(encode_mojo_type(value.value_type.ptr()[]))
    fields["is_const"] = ArcPointer(JSON.boolean(value.is_const))
    fields["kind"] = ArcPointer(JSON.string(value.kind.value()))
    fields["diagnostics"] = ArcPointer(_encode_list_mappingnote(value.diagnostics))
    fields["doc"] = ArcPointer(_encode_optional_doccomment(value.doc))
    return node("GlobalDecl", fields^)


def _decode_mojomodule(value: JSON) raises -> MojoModule:
    var fields = _fields(
        value,
        "MojoModule",
        "|source_header|library|link_name|link_mode|library_path_hint|dependencies|decls|",
    )
    var v_source_header = fields.ptr()[].get("source_header").ptr()[].text()
    var v_library = fields.ptr()[].get("library").ptr()[].text()
    var v_link_name = fields.ptr()[].get("link_name").ptr()[].text()
    var v_link_mode = _decode_linkmode(fields.ptr()[].get("link_mode").ptr()[])
    var v_library_path_hint: Optional[String] = {}
    if fields.ptr()[].has("library_path_hint"):
        v_library_path_hint = _decode_optional_string(
            fields.ptr()[].get("library_path_hint").ptr()[]
        )
    var v_dependencies: ModuleDependencies = ModuleDependencies()
    if fields.ptr()[].has("dependencies"):
        v_dependencies = _decode_moduledependencies(fields.ptr()[].get("dependencies").ptr()[])
    var v_decls: List[MojoDecl] = List[MojoDecl]()
    if fields.ptr()[].has("decls"):
        v_decls = _decode_list_mojodecl(fields.ptr()[].get("decls").ptr()[])
    return MojoModule(
        v_source_header^,
        v_library^,
        v_link_name^,
        v_link_mode^,
        v_library_path_hint^,
        v_dependencies^,
        v_decls^,
    )


def _encode_mojomodule(value: MojoModule) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["source_header"] = ArcPointer(JSON.string(value.source_header.copy()))
    fields["library"] = ArcPointer(JSON.string(value.library.copy()))
    fields["link_name"] = ArcPointer(JSON.string(value.link_name.copy()))
    fields["link_mode"] = ArcPointer(JSON.string(value.link_mode.value()))
    fields["library_path_hint"] = ArcPointer(_encode_optional_string(value.library_path_hint))
    fields["dependencies"] = ArcPointer(_encode_moduledependencies(value.dependencies))
    fields["decls"] = ArcPointer(_encode_list_mojodecl(value.decls))
    return node("MojoModule", fields^)


def decode_c_type(value: JSON) raises -> CType:
    var kind = value.get("kind").ptr()[].text()
    match kind:
        case "VoidType":
            return CType.void_type(_decode_voidtype(value))
        case "IntType":
            return CType.int_type(_decode_inttype(value))
        case "FloatType":
            return CType.float_type(_decode_floattype(value))
        case "QualifiedType":
            return CType.qualified_type(_decode_qualifiedtype(value))
        case "AtomicType":
            return CType.atomic_type(_decode_atomictype(value))
        case "CPointer":
            return CType.c_pointer(_decode_cpointer(value))
        case "CArray":
            return CType.c_array(_decode_carray(value))
        case "CFunctionPtr":
            return CType.c_function_ptr(_decode_cfunctionptr(value))
        case "OpaqueRecordRef":
            return CType.opaque_record_ref(_decode_opaquerecordref(value))
        case "UnsupportedType":
            return CType.unsupported_type(_decode_unsupportedtype(value))
        case "ComplexType":
            return CType.complex_type(_decode_complextype(value))
        case "VectorType":
            return CType.vector_type(_decode_vectortype(value))
        case "StructRef":
            return CType.struct_ref(_decode_structref(value))
        case "EnumRef":
            return CType.enum_ref(_decode_enumref(value))
        case "TypeRef":
            return CType.type_ref(_decode_typeref(value))
        case _:
            raise Error("kind " + kind + " does not belong to CType")


def encode_c_type(value: CType) -> JSON:
    match value:
        case .void_type(v):
            return _encode_voidtype(v)
        case .int_type(v):
            return _encode_inttype(v)
        case .float_type(v):
            return _encode_floattype(v)
        case .qualified_type(v):
            return _encode_qualifiedtype(v)
        case .atomic_type(v):
            return _encode_atomictype(v)
        case .c_pointer(v):
            return _encode_cpointer(v)
        case .c_array(v):
            return _encode_carray(v)
        case .c_function_ptr(v):
            return _encode_cfunctionptr(v)
        case .opaque_record_ref(v):
            return _encode_opaquerecordref(v)
        case .unsupported_type(v):
            return _encode_unsupportedtype(v)
        case .complex_type(v):
            return _encode_complextype(v)
        case .vector_type(v):
            return _encode_vectortype(v)
        case .struct_ref(v):
            return _encode_structref(v)
        case .enum_ref(v):
            return _encode_enumref(v)
        case .type_ref(v):
            return _encode_typeref(v)


def decode_mojo_type(value: JSON) raises -> MojoType:
    var kind = value.get("kind").ptr()[].text()
    match kind:
        case "BuiltinType":
            return MojoType.builtin_type(_decode_builtintype(value))
        case "NamedType":
            return MojoType.named_type(_decode_namedtype(value))
        case "MojoPointer":
            return MojoType.mojo_pointer(_decode_mojopointer(value))
        case "MojoArray":
            return MojoType.mojo_array(_decode_mojoarray(value))
        case "MojoFunctionPtr":
            return MojoType.mojo_function_ptr(_decode_mojofunctionptr(value))
        case "ParametricType":
            return MojoType.parametric_type(_decode_parametrictype(value))
        case _:
            raise Error("kind " + kind + " does not belong to MojoType")


def encode_mojo_type(value: MojoType) -> JSON:
    match value:
        case .builtin_type(v):
            return _encode_builtintype(v)
        case .named_type(v):
            return _encode_namedtype(v)
        case .mojo_pointer(v):
            return _encode_mojopointer(v)
        case .mojo_array(v):
            return _encode_mojoarray(v)
        case .mojo_function_ptr(v):
            return _encode_mojofunctionptr(v)
        case .parametric_type(v):
            return _encode_parametrictype(v)


def decode_parametric_arg(value: JSON) raises -> ParametricArg:
    var kind = value.get("kind").ptr()[].text()
    match kind:
        case "DTypeArg":
            return ParametricArg.d_type_arg(_decode_dtypearg(value))
        case "ConstArg":
            return ParametricArg.const_arg(_decode_constarg(value))
        case "NameArg":
            return ParametricArg.name_arg(_decode_namearg(value))
        case "TypeArg":
            return ParametricArg.type_arg(_decode_typearg(value))
        case _:
            raise Error("kind " + kind + " does not belong to ParametricArg")


def encode_parametric_arg(value: ParametricArg) -> JSON:
    match value:
        case .d_type_arg(v):
            return _encode_dtypearg(v)
        case .const_arg(v):
            return _encode_constarg(v)
        case .name_arg(v):
            return _encode_namearg(v)
        case .type_arg(v):
            return _encode_typearg(v)


def decode_c_expr(value: JSON) raises -> CConstExpr:
    var kind = value.get("kind").ptr()[].text()
    match kind:
        case "IntLiteral":
            return CConstExpr.int_literal(_decode_intliteral(value))
        case "CFloatLiteral":
            return CConstExpr.c_float_literal(_decode_cfloatliteral(value))
        case "StringLiteral":
            return CConstExpr.string_literal(_decode_stringliteral(value))
        case "CharLiteral":
            return CConstExpr.char_literal(_decode_charliteral(value))
        case "CNullPtrLiteral":
            return CConstExpr.c_null_ptr_literal(_decode_cnullptrliteral(value))
        case "CRefExpr":
            return CConstExpr.c_ref_expr(_decode_crefexpr(value))
        case "CUnaryExpr":
            return CConstExpr.c_unary_expr(_decode_cunaryexpr(value))
        case "CBinaryExpr":
            return CConstExpr.c_binary_expr(_decode_cbinaryexpr(value))
        case "CCastExpr":
            return CConstExpr.c_cast_expr(_decode_ccastexpr(value))
        case "CSizeOfExpr":
            return CConstExpr.c_size_of_expr(_decode_csizeofexpr(value))
        case "CCallExpr":
            return CConstExpr.c_call_expr(_decode_ccallexpr(value))
        case _:
            raise Error("kind " + kind + " does not belong to CConstExpr")


def encode_c_expr(value: CConstExpr) -> JSON:
    match value:
        case .int_literal(v):
            return _encode_intliteral(v)
        case .c_float_literal(v):
            return _encode_cfloatliteral(v)
        case .string_literal(v):
            return _encode_stringliteral(v)
        case .char_literal(v):
            return _encode_charliteral(v)
        case .c_null_ptr_literal(v):
            return _encode_cnullptrliteral(v)
        case .c_ref_expr(v):
            return _encode_crefexpr(v)
        case .c_unary_expr(v):
            return _encode_cunaryexpr(v)
        case .c_binary_expr(v):
            return _encode_cbinaryexpr(v)
        case .c_cast_expr(v):
            return _encode_ccastexpr(v)
        case .c_size_of_expr(v):
            return _encode_csizeofexpr(v)
        case .c_call_expr(v):
            return _encode_ccallexpr(v)


def decode_mojo_expr(value: JSON) raises -> MojoConstExpr:
    var kind = value.get("kind").ptr()[].text()
    match kind:
        case "IntLiteral":
            return MojoConstExpr.int_literal(_decode_intliteral(value))
        case "MojoFloatLiteral":
            return MojoConstExpr.mojo_float_literal(_decode_mojofloatliteral(value))
        case "StringLiteral":
            return MojoConstExpr.string_literal(_decode_stringliteral(value))
        case "CharLiteral":
            return MojoConstExpr.char_literal(_decode_charliteral(value))
        case "MojoRefExpr":
            return MojoConstExpr.mojo_ref_expr(_decode_mojorefexpr(value))
        case "MojoUnaryExpr":
            return MojoConstExpr.mojo_unary_expr(_decode_mojounaryexpr(value))
        case "MojoBinaryExpr":
            return MojoConstExpr.mojo_binary_expr(_decode_mojobinaryexpr(value))
        case "MojoCastExpr":
            return MojoConstExpr.mojo_cast_expr(_decode_mojocastexpr(value))
        case "MojoSizeOfExpr":
            return MojoConstExpr.mojo_size_of_expr(_decode_mojosizeofexpr(value))
        case "MojoCallExpr":
            return MojoConstExpr.mojo_call_expr(_decode_mojocallexpr(value))
        case _:
            raise Error("kind " + kind + " does not belong to MojoConstExpr")


def encode_mojo_expr(value: MojoConstExpr) -> JSON:
    match value:
        case .int_literal(v):
            return _encode_intliteral(v)
        case .mojo_float_literal(v):
            return _encode_mojofloatliteral(v)
        case .string_literal(v):
            return _encode_stringliteral(v)
        case .char_literal(v):
            return _encode_charliteral(v)
        case .mojo_ref_expr(v):
            return _encode_mojorefexpr(v)
        case .mojo_unary_expr(v):
            return _encode_mojounaryexpr(v)
        case .mojo_binary_expr(v):
            return _encode_mojobinaryexpr(v)
        case .mojo_cast_expr(v):
            return _encode_mojocastexpr(v)
        case .mojo_size_of_expr(v):
            return _encode_mojosizeofexpr(v)
        case .mojo_call_expr(v):
            return _encode_mojocallexpr(v)


def decode_decl(value: JSON) raises -> Decl:
    var kind = value.get("kind").ptr()[].text()
    match kind:
        case "Function":
            return Decl.function(_decode_function(value))
        case "Struct":
            return Decl.struct_decl(_decode_struct(value))
        case "Enum":
            return Decl.enum_decl(_decode_enum(value))
        case "Typedef":
            return Decl.typedef(_decode_typedef(value))
        case "Const":
            return Decl.const_decl(_decode_const(value))
        case "MacroDecl":
            return Decl.macro_decl(_decode_macrodecl(value))
        case "GlobalVar":
            return Decl.global_var(_decode_globalvar(value))
        case _:
            raise Error("kind " + kind + " does not belong to Decl")


def encode_decl(value: Decl) -> JSON:
    match value:
        case .function(v):
            return _encode_function(v)
        case .struct_decl(v):
            return _encode_struct(v)
        case .enum_decl(v):
            return _encode_enum(v)
        case .typedef(v):
            return _encode_typedef(v)
        case .const_decl(v):
            return _encode_const(v)
        case .macro_decl(v):
            return _encode_macrodecl(v)
        case .global_var(v):
            return _encode_globalvar(v)


def decode_mojo_decl(value: JSON) raises -> MojoDecl:
    var kind = value.get("kind").ptr()[].text()
    match kind:
        case "StructDecl":
            return MojoDecl.struct_decl(_decode_structdecl(value))
        case "AliasDecl":
            return MojoDecl.alias_decl(_decode_aliasdecl(value))
        case "FunctionDecl":
            return MojoDecl.function_decl(_decode_functiondecl(value))
        case "GlobalDecl":
            return MojoDecl.global_decl(_decode_globaldecl(value))
        case _:
            raise Error("kind " + kind + " does not belong to MojoDecl")


def encode_mojo_decl(value: MojoDecl) -> JSON:
    match value:
        case .struct_decl(v):
            return _encode_structdecl(v)
        case .alias_decl(v):
            return _encode_aliasdecl(v)
        case .function_decl(v):
            return _encode_functiondecl(v)
        case .global_decl(v):
            return _encode_globaldecl(v)


def decode_struct_member(value: JSON) raises -> StructMember:
    var kind = value.get("kind").ptr()[].text()
    match kind:
        case "StoredMember":
            return StructMember.stored_member(_decode_storedmember(value))
        case "PaddingMember":
            return StructMember.padding_member(_decode_paddingmember(value))
        case "OpaqueStorageMember":
            return StructMember.opaque_storage_member(_decode_opaquestoragemember(value))
        case "BitfieldGroupMember":
            return StructMember.bitfield_group_member(_decode_bitfieldgroupmember(value))
        case _:
            raise Error("kind " + kind + " does not belong to StructMember")


def encode_struct_member(value: StructMember) -> JSON:
    match value:
        case .stored_member(v):
            return _encode_storedmember(v)
        case .padding_member(v):
            return _encode_paddingmember(v)
        case .opaque_storage_member(v):
            return _encode_opaquestoragemember(v)
        case .bitfield_group_member(v):
            return _encode_bitfieldgroupmember(v)


def loads_c_type(text: String) raises -> CType:
    return decode_c_type(parse_json(text))


def dumps_c_type(value: CType) -> String:
    return dump_json(encode_c_type(value))


def loads_mojo_type(text: String) raises -> MojoType:
    return decode_mojo_type(parse_json(text))


def dumps_mojo_type(value: MojoType) -> String:
    return dump_json(encode_mojo_type(value))


def loads_c_expr(text: String) raises -> CConstExpr:
    return decode_c_expr(parse_json(text))


def dumps_c_expr(value: CConstExpr) -> String:
    return dump_json(encode_c_expr(value))


def loads_mojo_expr(text: String) raises -> MojoConstExpr:
    return decode_mojo_expr(parse_json(text))


def dumps_mojo_expr(value: MojoConstExpr) -> String:
    return dump_json(encode_mojo_expr(value))


def decode_target_abi(value: JSON) raises -> TargetABI:
    return _decode_targetabi(value)


def decode_cir(value: JSON) raises -> Unit:
    return _decode_unit(value)


def encode_cir(value: Unit) -> JSON:
    return _encode_unit(value)


def loads_cir(text: String) raises -> Unit:
    return decode_cir(parse_json(text))


def dumps_cir(value: Unit) -> String:
    return dump_json(encode_cir(value))


def decode_mojo_ir(value: JSON) raises -> MojoModule:
    return _decode_mojomodule(value)


def encode_mojo_ir(value: MojoModule) -> JSON:
    return _encode_mojomodule(value)


def loads_mojo_ir(text: String) raises -> MojoModule:
    return decode_mojo_ir(parse_json(text))


def dumps_mojo_ir(value: MojoModule) -> String:
    return dump_json(encode_mojo_ir(value))

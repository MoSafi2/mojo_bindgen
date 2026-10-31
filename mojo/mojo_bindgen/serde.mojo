"""Current-model type debug codecs. JSON is unversioned and stage-checked."""

from std.memory import ArcPointer
from .ir import *
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


def _decode_optional_arcpointer_ctype(value: JSON) raises -> Optional[ArcPointer[CType]]:
    if value.is_null():
        return {}
    return ArcPointer(decode_c_type(value))


def _encode_optional_arcpointer_ctype(value: Optional[ArcPointer[CType]]) -> JSON:
    if value:
        return encode_c_type(value.value().ptr()[])
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
    var v_value = fields.ptr()[].get("value").ptr()[].int_value()
    return ConstArg(v_value)


def _encode_constarg(value: ConstArg) -> JSON:
    var fields = Dict[String, ArcPointer[JSON]]()
    fields["value"] = ArcPointer(JSON.integer(value.value))
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


def loads_c_type(text: String) raises -> CType:
    return decode_c_type(parse_json(text))


def dumps_c_type(value: CType) -> String:
    return dump_json(encode_c_type(value))


def loads_mojo_type(text: String) raises -> MojoType:
    return decode_mojo_type(parse_json(text))


def dumps_mojo_type(value: MojoType) -> String:
    return dump_json(encode_mojo_type(value))


def decode_target_abi(value: JSON) raises -> TargetABI:
    return _decode_targetabi(value)

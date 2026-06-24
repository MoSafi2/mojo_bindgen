"""Clang scalar type lowering to IR primitives.

Port of `mojo_bindgen/parsing/lowering/primitive.py` for the Mojo parser path.
This targets `libclang_mojo`, which closely mirrors the Python bindings.
"""

import clang.cindex as cx
from mojo.ir import FloatKind, FloatType, IntKind, IntType, VoidType, Value, Object


def default_signed_int_primitive() -> IntType:
    """Return the parser's default signed int primitive fallback."""
    return IntType(
        kind="IntType",
        int_kind=IntKind.INT,
        size_bytes=4,
        align_bytes=Optional[Int](4),
        ext_bits=None,
    )


def _void_type_node() raises -> Value:
    var ob = Object()
    ob["kind"] = "VoidType"
    return Value(ob^)


def _int_type_node(node: IntType) raises -> Value:
    var ob = Object()
    ob["kind"] = "IntType"
    ob["int_kind"] = node.int_kind
    ob["size_bytes"] = node.size_bytes
    if node.align_bytes:
        ob["align_bytes"] = node.align_bytes.value()
    else:
        ob["align_bytes"] = None
    if node.ext_bits:
        ob["ext_bits"] = node.ext_bits.value()
    else:
        ob["ext_bits"] = None
    return Value(ob^)


def _float_type_node(node: FloatType) raises -> Value:
    var ob = Object()
    ob["kind"] = "FloatType"
    ob["float_kind"] = node.float_kind
    ob["size_bytes"] = node.size_bytes
    if node.align_bytes:
        ob["align_bytes"] = node.align_bytes.value()
    else:
        ob["align_bytes"] = None
    return Value(ob^)


def _normalize_spelling(spelling: String) -> String:
    var cleaned = spelling.replace("\t", " ")
    cleaned = cleaned.replace("\n", " ")
    cleaned = cleaned.replace("\r", " ")
    cleaned = cleaned.replace("( ", "(")
    cleaned = cleaned.replace(" )", ")")

    var result = ""
    var first = True
    for part in cleaned.split(" "):
        if part == "":
            continue
        if part == "const" or part == "volatile" or part == "restrict":
            continue
        if not first:
            result += " "
        result += part
        first = False
    return result


def _size_bytes(clang_type: cx.Type) -> Int:
    try:
        var size = clang_type.size()
        if size > 0:
            return size
    except:
        pass
    return 0


def _align_bytes(clang_type: cx.Type) -> Optional[Int]:
    try:
        var align = clang_type.align()
        if align > 0:
            return Optional[Int](align)
    except:
        pass
    return None


def _char_int_kind(
    clang_type: cx.Type, norm: String
) raises -> Optional[String]:
    if norm != "char":
        return None
    if clang_type.kind() == cx.TypeKind.CHAR_S:
        return Optional[String](IntKind.CHAR_S)
    if clang_type.kind() == cx.TypeKind.CHAR_U:
        return Optional[String](IntKind.CHAR_U)
    return None


def _parse_positive_int(text: String) -> Optional[Int]:
    try:
        var value = Int(String(text.strip()))
        if value >= 0:
            return Optional[Int](value)
    except:
        pass
    return None


def _ext_int_bits(norm: String) -> Optional[Int]:
    for token in norm.split(" "):
        if token.startswith("_BitInt(") and token.endswith(")"):
            var inner = token.replace("_BitInt(", "")
            return _parse_positive_int(String(inner.strip(")")))
        if token.startswith("_ExtInt(") and token.endswith(")"):
            var inner = token.replace("_ExtInt(", "")
            return _parse_positive_int(String(inner.strip(")")))
    return None


def _int_kind_by_type(kind: cx.TypeKind) -> Optional[String]:
    if kind == cx.TypeKind.BOOL:
        return Optional[String](IntKind.BOOL)
    if kind == cx.TypeKind.SCHAR:
        return Optional[String](IntKind.SCHAR)
    if kind == cx.TypeKind.UCHAR:
        return Optional[String](IntKind.UCHAR)
    if kind == cx.TypeKind.SHORT:
        return Optional[String](IntKind.SHORT)
    if kind == cx.TypeKind.USHORT:
        return Optional[String](IntKind.USHORT)
    if kind == cx.TypeKind.INT:
        return Optional[String](IntKind.INT)
    if kind == cx.TypeKind.UINT:
        return Optional[String](IntKind.UINT)
    if kind == cx.TypeKind.LONG:
        return Optional[String](IntKind.LONG)
    if kind == cx.TypeKind.ULONG:
        return Optional[String](IntKind.ULONG)
    if kind == cx.TypeKind.LONG_LONG:
        return Optional[String](IntKind.LONGLONG)
    if kind == cx.TypeKind.ULONG_LONG:
        return Optional[String](IntKind.ULONGLONG)
    if kind == cx.TypeKind.INT128:
        return Optional[String](IntKind.INT128)
    if kind == cx.TypeKind.UINT128:
        return Optional[String](IntKind.UINT128)
    if kind == cx.TypeKind.WCHAR:
        return Optional[String](IntKind.WCHAR)
    if kind == cx.TypeKind.CHAR16:
        return Optional[String](IntKind.CHAR16)
    if kind == cx.TypeKind.CHAR32:
        return Optional[String](IntKind.CHAR32)
    return None


def _float_kind_by_type(kind: cx.TypeKind) -> Optional[String]:
    if kind == cx.TypeKind.HALF:
        return Optional[String](FloatKind.FLOAT16)
    if kind == cx.TypeKind.FLOAT:
        return Optional[String](FloatKind.FLOAT)
    if kind == cx.TypeKind.DOUBLE:
        return Optional[String](FloatKind.DOUBLE)
    if kind == cx.TypeKind.LONG_DOUBLE:
        return Optional[String](FloatKind.LONG_DOUBLE)
    return None


struct PrimitiveResolver(Copyable, Movable):
    """Stateless lowering of clang scalar types to IR primitives."""

    def __init__(out self):
        pass

    def resolve_primitive(self, clang_type: cx.Type) raises -> Optional[Value]:
        """Return a scalar IR node for scalar clang types, else `None`."""
        var canonical = clang_type.canonical()
        var norm = _normalize_spelling(canonical.spelling())
        var size_bytes = _size_bytes(canonical)
        var align_bytes = _align_bytes(canonical)
        var kind = canonical.kind()

        if kind == cx.TypeKind.VOID:
            return Optional[Value](_void_type_node())

        if norm.find("__float128") != -1 or norm.find("_Float128") != -1:
            return Optional[Value](
                _float_type_node(
                    FloatType(
                        kind="FloatType",
                        float_kind=FloatKind.FLOAT128,
                        size_bytes=size_bytes,
                        align_bytes=align_bytes,
                    )
                )
            )

        var float_kind = _float_kind_by_type(kind)
        if float_kind:
            return Optional[Value](
                _float_type_node(
                    FloatType(
                        kind="FloatType",
                        float_kind=float_kind.value(),
                        size_bytes=size_bytes,
                        align_bytes=align_bytes,
                    )
                )
            )

        var int_kind = _char_int_kind(canonical, norm)
        if not int_kind:
            int_kind = _int_kind_by_type(kind)

        var ext_bits = _ext_int_bits(norm)
        if int_kind:
            return Optional[Value](
                _int_type_node(
                    IntType(
                        kind="IntType",
                        int_kind=int_kind.value(),
                        size_bytes=size_bytes,
                        align_bytes=align_bytes,
                        ext_bits=ext_bits,
                    )
                )
            )

        if ext_bits:
            return Optional[Value](
                _int_type_node(
                    IntType(
                        kind="IntType",
                        int_kind=IntKind.EXT_INT,
                        size_bytes=size_bytes,
                        align_bytes=align_bytes,
                        ext_bits=ext_bits,
                    )
                )
            )

        return None

"""Stateless Clang scalar resolution with source ABI geometry."""
from clang.cindex import Type, TypeKind
from ...ir import CType, IntType, IntKind, FloatType, FloatKind, VoidType


def safe_align(ref t: Type) raises -> Optional[Int]:
    var value = t.align()
    return Optional[Int](value) if value > 0 else Optional[Int]()


def safe_size(ref t: Type) raises -> Optional[Int]:
    var value = t.size()
    return Optional[Int](value) if value > 0 else Optional[Int]()


def default_int() -> IntType:
    return IntType(IntKind.INT, 4, 4)


def primitive(ref source: Type) raises -> Optional[CType]:
    var t = source.canonical()
    var spelling = t.spelling()
    var size = max(t.size(), 0)
    var align = safe_align(t)
    var kind = t.kind()
    if kind == TypeKind.VOID:
        return CType.void_type(VoidType())
    var fk = Optional[FloatKind]()
    if "__float128" in spelling or "_Float128" in spelling:
        fk = FloatKind.FLOAT128
    elif kind == TypeKind.HALF:
        fk = FloatKind.FLOAT16
    elif kind == TypeKind.FLOAT:
        fk = FloatKind.FLOAT
    elif kind == TypeKind.DOUBLE:
        fk = FloatKind.DOUBLE
    elif kind == TypeKind.LONG_DOUBLE:
        fk = FloatKind.LONG_DOUBLE
    if fk:
        return CType.float_type(FloatType(fk.value(), size, align.copy()))
    var ik = Optional[IntKind]()
    if kind == TypeKind.BOOL:
        ik = IntKind.BOOL
    elif kind == TypeKind.CHAR_S:
        ik = IntKind.CHAR_S
    elif kind == TypeKind.CHAR_U:
        ik = IntKind.CHAR_U
    elif kind == TypeKind.SCHAR:
        ik = IntKind.SCHAR
    elif kind == TypeKind.UCHAR:
        ik = IntKind.UCHAR
    elif kind == TypeKind.SHORT:
        ik = IntKind.SHORT
    elif kind == TypeKind.USHORT:
        ik = IntKind.USHORT
    elif kind == TypeKind.INT:
        ik = IntKind.INT
    elif kind == TypeKind.UINT:
        ik = IntKind.UINT
    elif kind == TypeKind.LONG:
        ik = IntKind.LONG
    elif kind == TypeKind.ULONG:
        ik = IntKind.ULONG
    elif kind == TypeKind.LONG_LONG:
        ik = IntKind.LONGLONG
    elif kind == TypeKind.ULONG_LONG:
        ik = IntKind.ULONGLONG
    elif kind == TypeKind.INT128:
        ik = IntKind.INT128
    elif kind == TypeKind.UINT128:
        ik = IntKind.UINT128
    elif kind == TypeKind.WCHAR:
        ik = IntKind.WCHAR
    elif kind == TypeKind.CHAR16:
        ik = IntKind.CHAR16
    elif kind == TypeKind.CHAR32:
        ik = IntKind.CHAR32
    var bits = Optional[Int]()
    if "_BitInt(" in spelling or "_ExtInt(" in spelling:
        var start = spelling.find("(") + 1
        var end = spelling.find(")")
        if start > 0 and end > start:
            bits = Int(String(spelling[byte=start:end]))
            if not ik:
                ik = IntKind.EXT_INT
    if ik:
        return CType.int_type(IntType(ik.value(), size, align.copy(), bits.copy()))
    return None

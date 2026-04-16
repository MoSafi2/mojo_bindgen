"""Primitive classification and literal ABI probing for parser lowering."""

from __future__ import annotations

import re
from dataclasses import dataclass

import clang.cindex as cx

from mojo_bindgen.ir import FloatKind, FloatType, IntKind, IntType, Type, VoidType
from mojo_bindgen.utils import build_c_parse_args


@dataclass(frozen=True)
class BuiltinScalarSpelling:
    """Kind metadata for canonical scalar C spellings."""

    scalar: Type


def _int(int_kind: IntKind, size_bytes: int | None = None) -> IntType:
    size = 0 if size_bytes is None else size_bytes
    return IntType(int_kind=int_kind, size_bytes=size)


def _float(float_kind: FloatKind, size_bytes: int | None = None) -> FloatType:
    size = 0 if size_bytes is None else size_bytes
    return FloatType(float_kind=float_kind, size_bytes=size)


_SCALAR_SPELLINGS: dict[str, BuiltinScalarSpelling] = {
    "void": BuiltinScalarSpelling(VoidType()),
    "_Bool": BuiltinScalarSpelling(_int(IntKind.BOOL)),
    "char": BuiltinScalarSpelling(_int(IntKind.CHAR_S)),
    "signed char": BuiltinScalarSpelling(_int(IntKind.SCHAR)),
    "unsigned char": BuiltinScalarSpelling(_int(IntKind.UCHAR)),
    "short": BuiltinScalarSpelling(_int(IntKind.SHORT)),
    "short int": BuiltinScalarSpelling(_int(IntKind.SHORT)),
    "signed short": BuiltinScalarSpelling(_int(IntKind.SHORT)),
    "signed short int": BuiltinScalarSpelling(_int(IntKind.SHORT)),
    "unsigned short": BuiltinScalarSpelling(_int(IntKind.USHORT)),
    "unsigned short int": BuiltinScalarSpelling(_int(IntKind.USHORT)),
    "int": BuiltinScalarSpelling(_int(IntKind.INT)),
    "signed": BuiltinScalarSpelling(_int(IntKind.INT)),
    "signed int": BuiltinScalarSpelling(_int(IntKind.INT)),
    "unsigned": BuiltinScalarSpelling(_int(IntKind.UINT)),
    "unsigned int": BuiltinScalarSpelling(_int(IntKind.UINT)),
    "long": BuiltinScalarSpelling(_int(IntKind.LONG)),
    "long int": BuiltinScalarSpelling(_int(IntKind.LONG)),
    "signed long": BuiltinScalarSpelling(_int(IntKind.LONG)),
    "unsigned long": BuiltinScalarSpelling(_int(IntKind.ULONG)),
    "unsigned long int": BuiltinScalarSpelling(_int(IntKind.ULONG)),
    "long long": BuiltinScalarSpelling(_int(IntKind.LONGLONG)),
    "long long int": BuiltinScalarSpelling(_int(IntKind.LONGLONG)),
    "signed long long": BuiltinScalarSpelling(_int(IntKind.LONGLONG)),
    "signed long long int": BuiltinScalarSpelling(_int(IntKind.LONGLONG)),
    "unsigned long long": BuiltinScalarSpelling(_int(IntKind.ULONGLONG)),
    "unsigned long long int": BuiltinScalarSpelling(_int(IntKind.ULONGLONG)),
    "float": BuiltinScalarSpelling(_float(FloatKind.FLOAT)),
    "double": BuiltinScalarSpelling(_float(FloatKind.DOUBLE)),
    "long double": BuiltinScalarSpelling(_float(FloatKind.LONG_DOUBLE)),
}


_LITERAL_SUFFIX_PREWARM: frozenset[str] = frozenset(
    {
        "",
        "u",
        "U",
        "l",
        "L",
        "ll",
        "LL",
        "ul",
        "uL",
        "Ul",
        "UL",
        "lu",
        "lU",
        "Lu",
        "LU",
        "llu",
        "llU",
        "LLu",
        "LLU",
        "ull",
        "uLL",
        "Ull",
        "ULL",
    }
)


SCALAR_KINDS = {
    cx.TypeKind.BOOL,
    cx.TypeKind.CHAR_U,
    cx.TypeKind.UCHAR,
    cx.TypeKind.CHAR16,
    cx.TypeKind.CHAR32,
    cx.TypeKind.USHORT,
    cx.TypeKind.UINT,
    cx.TypeKind.ULONG,
    cx.TypeKind.ULONGLONG,
    cx.TypeKind.UINT128,
    cx.TypeKind.CHAR_S,
    cx.TypeKind.SCHAR,
    cx.TypeKind.WCHAR,
    cx.TypeKind.SHORT,
    cx.TypeKind.INT,
    cx.TypeKind.LONG,
    cx.TypeKind.LONGLONG,
    cx.TypeKind.INT128,
    cx.TypeKind.FLOAT,
    cx.TypeKind.DOUBLE,
    cx.TypeKind.LONGDOUBLE,
    cx.TypeKind.HALF,
}


SIGNED_INT_KINDS = {
    cx.TypeKind.CHAR_S,
    cx.TypeKind.SCHAR,
    cx.TypeKind.SHORT,
    cx.TypeKind.INT,
    cx.TypeKind.LONG,
    cx.TypeKind.LONGLONG,
    cx.TypeKind.INT128,
}


FLOAT_KINDS = {
    cx.TypeKind.FLOAT,
    cx.TypeKind.DOUBLE,
    cx.TypeKind.LONGDOUBLE,
    cx.TypeKind.HALF,
}


def default_signed_int_primitive() -> IntType:
    """Return the parser's default signed int primitive fallback."""
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _c_integer_spelling_for_literal_suffix(suffix: str) -> str:
    """Map a C integer literal suffix to a canonical integer spelling."""
    if not suffix:
        return "int"
    s = suffix.lower()
    has_u = "u" in s
    l_count = s.count("l")
    if l_count >= 2:
        return "unsigned long long" if has_u else "long long"
    if l_count == 1:
        return "unsigned long" if has_u else "long"
    return "unsigned int" if has_u else "int"


def _suffix_probe_parse_args(compile_args: list[str]) -> list[str]:
    """Build parse args for integer literal suffix type probes."""
    return build_c_parse_args(compile_args, default_std="-std=gnu11")


class PrimitiveResolver:
    """Scalar classification and integer-literal ABI probing."""

    def __init__(self, compile_args: list[str]) -> None:
        self.compile_args = list(compile_args)
        self._literal_suffix_cache: dict[str, IntType] = {}
        for suffix in _LITERAL_SUFFIX_PREWARM:
            self.primitive_for_integer_literal_suffix(suffix)

    def primitive_for_integer_literal_suffix(self, suffix: str) -> IntType:
        """Map an integer literal suffix to an ABI-correct primitive."""
        if suffix in self._literal_suffix_cache:
            return self._literal_suffix_cache[suffix]
        spelling = _c_integer_spelling_for_literal_suffix(suffix)
        idx = cx.Index.create()
        src = f"{spelling} __bindgen_m;\n"
        tu = idx.parse(
            "__bindgen_suffix_probe.c",
            args=_suffix_probe_parse_args(self.compile_args),
            unsaved_files=[("__bindgen_suffix_probe.c", src)],
            options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        prim: IntType | None = None
        for cursor in tu.cursor.get_children():
            if (
                cursor.kind == cx.CursorKind.VAR_DECL
                and cursor.spelling == "__bindgen_m"
            ):
                prim = self.make_primitive_from_kind(cursor.type)
                break
        if prim is None:
            prim = default_signed_int_primitive()
            if "unsigned" in spelling.split():
                prim = IntType(int_kind=IntKind.UINT, size_bytes=prim.size_bytes)
        self._literal_suffix_cache[suffix] = prim
        return prim

    def make_primitive_from_kind(self, clang_type: cx.Type) -> IntType:
        """Lower an integer-like clang type to an integer IR node."""
        scalar = self.resolve_primitive(clang_type)
        if not isinstance(scalar, IntType):
            return default_signed_int_primitive()
        return scalar

    @staticmethod
    def _size_and_align(canonical: cx.Type) -> tuple[int, int | None]:
        size_raw = canonical.get_size()
        align_raw = canonical.get_align()
        size_bytes = size_raw if size_raw > 0 else 0
        align_bytes = align_raw if align_raw > 0 else None
        return size_bytes, align_bytes

    @classmethod
    def _int_kind_for_type(cls, canonical: cx.Type, norm: str) -> IntKind:
        tk = canonical.kind
        if tk == cx.TypeKind.BOOL:
            return IntKind.BOOL
        if tk == cx.TypeKind.CHAR_S and norm == "char":
            return IntKind.CHAR_S
        if tk == cx.TypeKind.CHAR_U and norm == "char":
            return IntKind.CHAR_U
        if tk == cx.TypeKind.SCHAR:
            return IntKind.SCHAR
        if tk == cx.TypeKind.UCHAR:
            return IntKind.UCHAR
        if tk == cx.TypeKind.SHORT:
            return IntKind.SHORT
        if tk == cx.TypeKind.USHORT:
            return IntKind.USHORT
        if tk == cx.TypeKind.INT:
            return IntKind.INT
        if tk == cx.TypeKind.UINT:
            return IntKind.UINT
        if tk == cx.TypeKind.LONG:
            return IntKind.LONG
        if tk == cx.TypeKind.ULONG:
            return IntKind.ULONG
        if tk == cx.TypeKind.LONGLONG:
            return IntKind.LONGLONG
        if tk == cx.TypeKind.ULONGLONG:
            return IntKind.ULONGLONG
        if tk == cx.TypeKind.INT128:
            return IntKind.INT128
        if tk == cx.TypeKind.UINT128:
            return IntKind.UINT128
        if tk == cx.TypeKind.WCHAR:
            return IntKind.WCHAR
        if tk == cx.TypeKind.CHAR16:
            return IntKind.CHAR16
        if tk == cx.TypeKind.CHAR32:
            return IntKind.CHAR32
        return IntKind.EXT_INT

    @staticmethod
    def _float_kind_for_type(canonical: cx.Type, norm: str) -> FloatKind:
        tk = canonical.kind
        if tk == cx.TypeKind.HALF:
            return FloatKind.FLOAT16
        if tk == cx.TypeKind.FLOAT:
            return FloatKind.FLOAT
        if tk == cx.TypeKind.DOUBLE:
            return FloatKind.DOUBLE
        if tk == cx.TypeKind.LONGDOUBLE:
            return FloatKind.LONG_DOUBLE
        if "__float128" in norm or "_Float128" in norm:
            return FloatKind.FLOAT128
        return FloatKind.DOUBLE

    @staticmethod
    def _ext_int_bits(norm: str) -> int | None:
        match = re.search(r"(?:_BitInt|_ExtInt)\s*\(\s*(\d+)\s*\)", norm)
        return int(match.group(1)) if match else None

    def resolve_primitive(self, clang_type: cx.Type) -> Type | None:
        """Return a scalar IR node for scalar clang types, else ``None``."""
        canonical = clang_type.get_canonical()
        spelling = canonical.spelling
        norm = re.sub(r"\b(const|volatile|restrict)\b", "", spelling).strip()
        defaults = _SCALAR_SPELLINGS.get(norm)
        size_bytes, align_bytes = self._size_and_align(canonical)
        if defaults is not None:
            scalar = defaults.scalar
            if isinstance(scalar, VoidType):
                return scalar
            if isinstance(scalar, IntType):
                int_kind = scalar.int_kind
                if norm == "char" and canonical.kind == cx.TypeKind.CHAR_U:
                    int_kind = IntKind.CHAR_U
                return IntType(
                    int_kind=int_kind,
                    size_bytes=size_bytes,
                    align_bytes=align_bytes,
                )
            if isinstance(scalar, FloatType):
                return FloatType(
                    float_kind=scalar.float_kind,
                    size_bytes=size_bytes,
                    align_bytes=align_bytes,
                )

        tk = canonical.kind
        if tk == cx.TypeKind.VOID:
            return VoidType()
        if tk in FLOAT_KINDS or "__float128" in norm or "_Float128" in norm:
            return FloatType(
                float_kind=self._float_kind_for_type(canonical, norm),
                size_bytes=size_bytes,
                align_bytes=align_bytes,
            )
        if tk in SCALAR_KINDS:
            return IntType(
                int_kind=self._int_kind_for_type(canonical, norm),
                size_bytes=size_bytes,
                align_bytes=align_bytes,
                ext_bits=self._ext_int_bits(norm),
            )
        return None

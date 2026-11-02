"""Target geometry from Clang, never from the generator host's Mojo ABI."""
from clang.cindex import Index, UnsavedFile, CursorKind
from .frontend import normalized_args, children
from ..ir import TargetABI, ByteOrder, FloatABI, FloatFormat, FloatKind


def probe_target_abi(args: List[String]) raises -> TargetABI:
    var index = Index.create()
    var tu = index.parse(
        "__bindgen_target_abi_probe.c",
        normalized_args(args),
        [
            UnsavedFile(
                "__bindgen_target_abi_probe.c",
                "void *__bindgen_p;\nfloat __bindgen_float;\nenum { __bindgen_float_mant = __FLT_MANT_DIG__, __bindgen_float_exp = __FLT_MAX_EXP__ };\ndouble __bindgen_double;\nenum { __bindgen_double_mant = __DBL_MANT_DIG__, __bindgen_double_exp = __DBL_MAX_EXP__ };\nlong double __bindgen_long_double;\nenum { __bindgen_long_double_mant = __LDBL_MANT_DIG__, __bindgen_long_double_exp = __LDBL_MAX_EXP__ };\nenum { __bindgen_radix = __FLT_RADIX__ };\n",
            )
        ],
    )
    var info = tu.target_info()
    var triple = info.triple()
    var arch = String(triple.split("-")[0])
    var order = ByteOrder.LITTLE
    var big: List[String] = [
        "armeb",
        "aarch64_be",
        "m68k",
        "mips",
        "mips64",
        "ppc",
        "ppc64",
        "powerpc",
        "powerpc64",
        "s390x",
        "sparc",
        "sparcv9",
        "systemz",
        "thumbeb",
    ]
    var little: List[String] = [
        "aarch64",
        "arm",
        "armv4t",
        "armv5",
        "armv5e",
        "armv6",
        "armv6m",
        "armv7",
        "armv7a",
        "armv7m",
        "armv7r",
        "armv7s",
        "armv8",
        "armv8a",
        "armv8m.base",
        "armv8m.main",
        "arm64",
        "i386",
        "i486",
        "i586",
        "i686",
        "loongarch32",
        "loongarch64",
        "mipsel",
        "mips64el",
        "nvptx",
        "nvptx64",
        "riscv32",
        "riscv64",
        "wasm32",
        "wasm64",
        "x86_64",
        "x86",
        "xcore",
        "powerpc64le",
        "thumb",
        "thumbv6m",
        "thumbv7m",
        "thumbv7em",
        "thumbv7neon",
    ]
    if arch in big or arch.endswith("be") or arch.endswith("eb"):
        order = ByteOrder.BIG
    elif arch not in little and not arch.endswith("le") and not arch.endswith("el"):
        raise Error("could not determine byte order from target triple " + triple)
    var values = Dict[String, Int]()
    var shapes = Dict[String, Tuple[Int, Int]]()
    var root = tu.cursor()
    for cursor in children(root):
        if cursor.kind() == CursorKind.ENUM_DECL:
            for item in children(cursor):
                values[item.spelling()] = Int(item.enum_value())
        elif cursor.kind() == CursorKind.VAR_DECL:
            var shape = cursor.type()
            shapes[cursor.spelling()] = (shape.size(), shape.align())
    var floats = List[FloatABI]()
    var names: List[String] = ["float", "double", "long_double"]
    var kinds: List[FloatKind] = [FloatKind.FLOAT, FloatKind.DOUBLE, FloatKind.LONG_DOUBLE]
    for i in range(len(names)):
        var prefix = "__bindgen_" + names[i]
        var shape = shapes[prefix]
        var format = classify_float_format(
            values["__bindgen_radix"], values[prefix + "_mant"], values[prefix + "_exp"]
        )
        floats.append(FloatABI(kinds[i], format, shape[0], shape[1]))
    for cursor in children(root):
        if cursor.kind() == CursorKind.VAR_DECL and cursor.spelling() == "__bindgen_p":
            var shape = cursor.type()
            if shape.size() > 0 and shape.align() > 0:
                return TargetABI(shape.size(), shape.align(), order, triple.copy(), floats^)
    raise Error("could not derive pointer ABI facts from Clang")


def classify_float_format(radix: Int, mantissa: Int, exponent: Int) -> FloatFormat:
    if radix == 2:
        if mantissa == 11 and exponent == 16:
            return FloatFormat.BINARY16
        if mantissa == 24 and exponent == 128:
            return FloatFormat.BINARY32
        if mantissa == 53 and exponent == 1024:
            return FloatFormat.BINARY64
        if mantissa == 64 and exponent == 16384:
            return FloatFormat.X87_EXTENDED
        if mantissa == 113 and exponent == 16384:
            return FloatFormat.BINARY128
        if mantissa == 106 and exponent == 1024:
            return FloatFormat.DOUBLE_DOUBLE
    return FloatFormat.UNKNOWN

"""Target geometry from Clang, never from the generator host's Mojo ABI."""
from clang.cindex import Index, UnsavedFile, CursorKind
from .frontend import normalized_args, children
from ..ir import TargetABI, ByteOrder


def probe_target_abi(args: List[String]) raises -> TargetABI:
    var index = Index.create()
    var tu = index.parse(
        "__bindgen_target_abi_probe.c",
        normalized_args(args),
        [UnsavedFile("__bindgen_target_abi_probe.c", "void *__bindgen_p;\n")],
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
    var root = tu.cursor()
    for cursor in children(root):
        if cursor.kind() == CursorKind.VAR_DECL and cursor.spelling() == "__bindgen_p":
            var shape = cursor.type()
            if shape.size() > 0 and shape.align() > 0:
                return TargetABI(shape.size(), shape.align(), order, triple.copy())
    raise Error("could not derive pointer ABI facts from Clang")

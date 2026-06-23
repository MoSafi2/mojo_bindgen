# Clang-derived target ABI facts for one parse configuration.
#
# Ported from `mojo_bindgen/parsing/target_abi.py`.
# Workaround: libclang_mojo 0.1.0's TargetInfo.triple() is buggy;
# we call clang_TargetInfo_getTriple directly via FFI.

from clang.cindex import (
    Index,
    TranslationUnit,
    TranslationUnitFlags,
    UnsavedFile,
)
from clang._ffi import (
    clang_getTranslationUnitTargetInfo,
    clang_TargetInfo_getTriple,
    clang_TargetInfo_dispose,
    clang_getCString,
    clang_disposeString,
    CXString,
    CXTranslationUnit,
)
from clang.common import _borrow_c_string, UnsavedFileArena
from mojo.utils import build_c_parse_args
from mojo.ir import TargetABI, ByteOrder
from std.memory import alloc, UnsafePointer
from std.ffi import c_uint
from clang._ffi import clang_parseTranslationUnit2
from clang.common import _alloc_c_string, _c_string
from std.ffi import c_int, c_char
from clang.enums import ErrorCode as EC

comptime _PROBE_FILENAME = "__bindgen_target_abi_probe.c"
comptime _PROBE_DECL_NAME = "__bindgen_p"
comptime _PROBE_SOURCE = "void *" + _PROBE_DECL_NAME + ";\n"


def TargetABIProbeError(message: String) -> Error:
    """Create a TargetABIProbeError."""
    return Error("TargetABIProbeError: " + message)


def probe_target_abi(compile_args: List[String]) raises -> TargetABI:
    """Probe pointer ABI facts using Clang under the given compile args."""

    var idx = Index.create()
    var args = build_c_parse_args(compile_args, default_std="-std=gnu11")

    var unsaved = UnsavedFile(filename=_PROBE_FILENAME, contents=_PROBE_SOURCE)
    var unsaved_files: List[UnsavedFile] = [unsaved^]

    var tu = _parse_probe(idx, _PROBE_FILENAME, args, unsaved_files)

    # Get target triple via direct FFI
    var triple = _get_triple_direct(tu)

    # Determine byte order from arch
    var arch = _triple_arch(triple)
    var byte_order = _byte_order_from_arch(arch, triple)

    # Find the probe variable and get its size/align
    var root = tu.cursor()
    var children = root.children()
    var pointer_size = 0
    var pointer_align = 0
    for cursor in children:
        var spelling = cursor.spelling()
        if spelling == _PROBE_DECL_NAME:
            var t = cursor.type()
            pointer_size = max(0, t.size())
            pointer_align = max(0, t.align())
            break

    if pointer_size <= 0 or pointer_align <= 0:
        raise TargetABIProbeError(
            "could not derive pointer ABI facts from Clang"
        )

    var abi = TargetABI()
    abi.pointer_size_bytes = pointer_size
    abi.pointer_align_bytes = pointer_align
    abi.byte_order = byte_order
    return abi^


def _parse_probe(
    ref index: Index,
    path: String,
    args: List[String],
    unsaved_files: List[UnsavedFile],
) raises -> TranslationUnit:
    """Parse using the workaround for CStringArray bug."""

    var n = len(args)
    var cstrs: List[UnsafePointer[c_char, MutAnyOrigin]] = []

    comptime SlotType = Optional[UnsafePointer[c_char, ImmutUntrackedOrigin]]
    var slots_opt: Optional[
        UnsafePointer[SlotType, ImmutUntrackedOrigin]
    ] = None
    var slots_mut_opt: Optional[UnsafePointer[SlotType, MutAnyOrigin]] = None

    if n > 0:
        var slots = alloc[SlotType](n)
        slots_mut_opt = Optional[UnsafePointer[SlotType, MutAnyOrigin]](slots)
        for i in range(n):
            var s = _alloc_c_string(args[i])
            cstrs.append(s)
            slots[i] = SlotType(_c_string(s))
        slots_opt = Optional[UnsafePointer[SlotType, ImmutUntrackedOrigin]](
            rebind[UnsafePointer[SlotType, ImmutUntrackedOrigin]](slots)
        )

    var unsaved_arena = UnsavedFileArena(unsaved_files)

    var out_tu: CXTranslationUnit = CXTranslationUnit()
    var out_ptr = UnsafePointer[CXTranslationUnit, MutAnyOrigin](to=out_tu)

    var raw_err = clang_parseTranslationUnit2(
        index._raw_handle(),
        _borrow_c_string(path),
        slots_opt,
        c_int(n),
        unsaved_arena.ptr(),
        unsaved_arena.count(),
        TranslationUnitFlags.SKIP_FUNCTION_BODIES.as_c_uint(),
        rebind[UnsafePointer[CXTranslationUnit, MutUntrackedOrigin]](out_ptr),
    )

    for s in cstrs:
        s.free()
    if slots_mut_opt:
        slots_mut_opt.value().free()

    var err = EC(raw_err)
    if err != EC.SUCCESS:
        raise Error("parse failed: error code=" + String(Int(err.as_c_uint())))

    return TranslationUnit(index._shared_state(), out_tu)


def _get_triple_direct(tu: TranslationUnit) raises -> String:
    """Get the target triple via direct FFI (workaround for buggy TargetInfo.triple()).
    """
    var ti = clang_getTranslationUnitTargetInfo(tu._raw_handle())
    if not ti:
        raise Error("null target info")

    var cs_ptr = alloc[CXString](1)
    cs_ptr[] = CXString(data=None, private_flags=c_uint(0))

    clang_TargetInfo_getTriple(
        Optional[UnsafePointer[CXString, MutUntrackedOrigin]](cs_ptr),
        ti,
    )

    var c_str = clang_getCString(cs_ptr)
    var result = String("")
    if c_str:
        result = String(unsafe_from_utf8_ptr=c_str.value())

    clang_disposeString(cs_ptr)
    cs_ptr.free()
    clang_TargetInfo_dispose(ti)
    return result


def _triple_arch(triple: String) -> String:
    """Extract the architecture component from a target triple."""
    var parts = triple.split("-")
    if len(parts) > 0:
        return String(parts[0])
    return ""


def _is_big_endian_arch(arch: String) -> Bool:
    var archs = [
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
    for a in archs:
        if arch == a:
            return True
    return False


def _is_little_endian_arch(arch: String) -> Bool:
    var archs = [
        "aarch64",
        "arm",
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
    ]
    for a in archs:
        if arch == a:
            return True
    return False


def _byte_order_from_arch(arch: String, triple: String) raises -> String:
    """Determine byte order from the architecture name."""
    if _is_big_endian_arch(arch):
        return ByteOrder.BIG
    if arch.endswith("be") or arch.endswith("eb"):
        return ByteOrder.BIG
    if _is_little_endian_arch(arch):
        return ByteOrder.LITTLE
    if arch.endswith("le") or arch.endswith("el"):
        return ByteOrder.LITTLE
    raise TargetABIProbeError(
        "could not determine byte order from target triple " + triple
    )

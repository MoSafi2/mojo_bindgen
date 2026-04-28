"""Clang-derived target ABI facts for one parse configuration."""

from __future__ import annotations

import clang.cindex as cx

from mojo_bindgen.ir import ByteOrder, TargetABI
from mojo_bindgen.utils import build_c_parse_args

_PROBE_FILENAME = "__bindgen_target_abi_probe.c"
_PROBE_DECL_NAME = "__bindgen_p"
_PROBE_SOURCE = f"void *{_PROBE_DECL_NAME};\n"


class TargetABIProbeError(RuntimeError):
    """Raised when Clang target ABI facts cannot be probed."""


def _parse_args_for_probe(compile_args: list[str]) -> list[str]:
    return build_c_parse_args(compile_args, default_std="-std=gnu11")


def _extract_pointer_abi(tu: cx.TranslationUnit) -> TargetABI | None:
    _ensure_target_info_bindings()
    target_info = cx.conf.lib.clang_getTranslationUnitTargetInfo(tu)
    if not target_info:
        return None
    try:
        byte_order = _byte_order_from_target_info(target_info)
        for cursor in tu.cursor.get_children():
            if cursor.kind != cx.CursorKind.VAR_DECL or cursor.spelling != _PROBE_DECL_NAME:
                continue
            size_bytes = max(0, cursor.type.get_size())
            align_bytes = max(0, cursor.type.get_align())
            if size_bytes <= 0 or align_bytes <= 0:
                return None
            return TargetABI(
                pointer_size_bytes=size_bytes,
                pointer_align_bytes=align_bytes,
                byte_order=byte_order,
            )
        return None
    finally:
        cx.conf.lib.clang_TargetInfo_dispose(target_info)


def _byte_order_from_target_info(target_info: object) -> ByteOrder:
    triple = _target_triple_text(target_info)
    arch = triple.split("-", 1)[0]
    if arch in _BIG_ENDIAN_ARCHS or arch.endswith(("be", "eb")):
        return ByteOrder.BIG
    if arch in _LITTLE_ENDIAN_ARCHS or arch.endswith(("le", "el")):
        return ByteOrder.LITTLE
    raise TargetABIProbeError(f"could not determine byte order from target triple {triple!r}")


def _target_triple_text(target_info: object) -> str:
    triple = cx.conf.lib.clang_TargetInfo_getTriple(target_info)
    if not triple:
        raise TargetABIProbeError("could not determine target triple from Clang")
    return triple if isinstance(triple, str) else str(triple)


def _ensure_target_info_bindings() -> None:
    lib = cx.conf.lib
    if getattr(lib, "_bindgen_target_info_api_ready", False):
        return
    try:
        lib.clang_getTranslationUnitTargetInfo.argtypes = [cx.TranslationUnit]
        lib.clang_getTranslationUnitTargetInfo.restype = cx.c_object_p
        lib.clang_TargetInfo_getTriple.argtypes = [cx.c_object_p]
        lib.clang_TargetInfo_getTriple.restype = cx._CXString
        lib.clang_TargetInfo_getTriple.errcheck = cx._CXString.from_result
        lib.clang_TargetInfo_dispose.argtypes = [cx.c_object_p]
        lib.clang_TargetInfo_dispose.restype = None
    except AttributeError as exc:  # pragma: no cover - libclang compatibility guard
        raise TargetABIProbeError("libclang target-info APIs are unavailable") from exc
    setattr(lib, "_bindgen_target_info_api_ready", True)


_BIG_ENDIAN_ARCHS = {
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
}

_LITTLE_ENDIAN_ARCHS = {
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
}


def probe_target_abi(compile_args: list[str]) -> TargetABI:
    """Probe pointer ABI facts using Clang under the given compile args."""

    idx = cx.Index.create()
    tu = idx.parse(
        _PROBE_FILENAME,
        args=_parse_args_for_probe(compile_args),
        unsaved_files=[(_PROBE_FILENAME, _PROBE_SOURCE)],
        options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
    )
    target_abi = _extract_pointer_abi(tu)
    if target_abi is None:
        raise TargetABIProbeError("could not derive pointer ABI facts from Clang")
    return target_abi


__all__ = ["TargetABIProbeError", "probe_target_abi"]

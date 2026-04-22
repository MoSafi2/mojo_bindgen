"""Clang-derived target ABI facts for one parse configuration."""

from __future__ import annotations

import clang.cindex as cx

from mojo_bindgen.ir import TargetABI
from mojo_bindgen.utils import build_c_parse_args

_PROBE_FILENAME = "__bindgen_target_abi_probe.c"
_PROBE_DECL_NAME = "__bindgen_p"
_PROBE_SOURCE = f"void *{_PROBE_DECL_NAME};\n"


class TargetABIProbeError(RuntimeError):
    """Raised when Clang target ABI facts cannot be probed."""


def _parse_args_for_probe(compile_args: list[str]) -> list[str]:
    return build_c_parse_args(compile_args, default_std="-std=gnu11")


def _extract_pointer_abi(tu: cx.TranslationUnit) -> TargetABI | None:
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
        )
    return None


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

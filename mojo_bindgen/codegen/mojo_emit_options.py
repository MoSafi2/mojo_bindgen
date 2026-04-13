"""Options that configure Mojo code generation and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.codegen.lowering import FFIOriginStyle

LinkingMode = Literal["external_call", "owned_dl_handle"]
"""Supported linking strategies for generated wrappers."""


@dataclass
class MojoEmitOptions:
    """Controls Mojo code generation and rendering behavior.

    The options are shared by analysis and rendering. They shape link strategy,
    pointer provenance, generated comments, and alignment emission policy.
    """

    linking: LinkingMode = "external_call"
    """external_call: link C symbols at mojo build time; emitted wrappers use ``abi("C")``.
    owned_dl_handle: resolve via ``OwnedDLHandle.call`` (raises); wrappers omit ``abi("C")`` on
    the ``def`` line because ``abi("C")`` combined with ``raises`` currently fails LLVM lowering."""

    library_path_hint: str | None = None
    """If set with owned_dl_handle, pass this path to OwnedDLHandle(...). If None, use DEFAULT_RTLD (symbols must be linked into the process)."""

    module_comment: bool = True
    """Emit a leading comment with source header and library metadata."""

    warn_abi: bool = True
    """Emit comments reminding that packed/aligned layouts need verification."""

    ffi_origin: FFIOriginStyle = "external"
    """Pointer provenance for lowered types: ``external`` → Mut/Immut*ExternalOrigin (recommended for C FFI); ``any`` → *AnyOrigin."""

    emit_align: bool = True
    """If True, emit ``@align(N)`` from C ``Struct.align_bytes`` when valid (Mojo: power of 2, ``N > 1``, max ``2**29``)."""

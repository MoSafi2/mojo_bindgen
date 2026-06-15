"""Options that configure Mojo code generation and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LinkingMode = Literal[
    "external_call",
    "dylib_lazy",
    "dylib_checked",
    "owned_dl_handle",  # deprecated alias for dylib_checked
]
"""Supported linking strategies for generated wrappers."""


FFIOriginStyle = Literal["external", "any"]
"""Pointer provenance styles supported by the generated Mojo bindings."""


@dataclass
class MojoEmitOptions:
    """Controls Mojo code generation and rendering behavior.

    The options are shared by analysis and rendering. They shape link strategy,
    pointer provenance, and generated comments.
    """

    linking: LinkingMode = "external_call"
    """external_call: link C symbols at mojo build time; emitted wrappers are plain Mojo functions.
    dylib_lazy: load the shared library once and cache C-ABI function pointers via stdlib internals.
    dylib_checked: own the library in a generated API struct and raise on load/symbol errors.
    owned_dl_handle: deprecated alias for dylib_checked."""

    library_path_hint: str | None = None
    """If set with a dynamic link mode, try this path first when loading the shared library.
    If None, the generated code guesses platform-specific names such as lib<name>.so."""

    module_comment: bool = True
    """Emit a leading comment with source header and library metadata."""

    emit_doc_comments: bool = True
    """Emit captured source documentation comments into generated Mojo bindings."""

    warn_abi: bool = True
    """Emit comments reminding that packed/aligned layouts need verification."""

    strict_abi: bool = False
    """When true, preserve parsed C alignment emission behavior. When false, emit ``@align`` only for records with explicit layout intent such as packed or attribute-aligned declarations."""

    ffi_origin: FFIOriginStyle = "external"
    """Pointer provenance for mapped types: ``external`` → Mut/Immut*ExternalOrigin (recommended for C FFI); ``any`` → *AnyOrigin."""

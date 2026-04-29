"""C header → Mojo FFI bindings via libclang."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from mojo_bindgen.orchestrator import (
    BindgenOptions,
    BindgenOrchestrator,
    BindgenResult,
    bindgen,
)

try:
    __version__ = version("mojo-bindgen")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "BindgenOptions",
    "BindgenOrchestrator",
    "BindgenResult",
    "__version__",
    "bindgen",
]

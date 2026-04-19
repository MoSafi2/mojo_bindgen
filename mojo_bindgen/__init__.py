"""C header → Mojo FFI bindings via libclang."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from mojo_bindgen.codegen import MojoEmitOptions, MojoGenerator, generate_mojo

try:
    __version__ = version("mojo-bindgen")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "MojoEmitOptions",
    "MojoGenerator",
    "__version__",
    "generate_mojo",
]

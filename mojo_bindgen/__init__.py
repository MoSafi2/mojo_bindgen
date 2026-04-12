"""C header → Mojo FFI bindings via libclang."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mojo-bindgen")
except PackageNotFoundError:
    __version__ = "0.1.0"

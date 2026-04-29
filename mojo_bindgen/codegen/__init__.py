"""Public Mojo code generation API.

Import from this package when you want the printer-facing codegen surface
rather than the individual implementation modules.
"""

from mojo_bindgen.codegen.mojo_ir_printer import (
    MojoIRPrinter,
    MojoIRPrintOptions,
    render_mojo_module,
)
from mojo_bindgen.codegen.normalize_mojo_module import (
    NormalizeMojoModuleError,
    NormalizeMojoModulePass,
    normalize_mojo_module,
)
from mojo_bindgen.layout_tests import render_layout_test_module

__all__ = [
    "NormalizeMojoModuleError",
    "NormalizeMojoModulePass",
    "MojoIRPrinter",
    "MojoIRPrintOptions",
    "normalize_mojo_module",
    "render_layout_test_module",
    "render_mojo_module",
]

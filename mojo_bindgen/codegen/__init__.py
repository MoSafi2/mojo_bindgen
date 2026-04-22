"""Public Mojo code generation API.

Import from this package when you want the printer-facing codegen surface
rather than the individual implementation modules.
"""

from mojo_bindgen.codegen.mojo_ir_printer import (
    MojoIRPrinter,
    MojoIRPrintOptions,
    render_mojo_module,
)

__all__ = [
    "MojoIRPrinter",
    "MojoIRPrintOptions",
    "render_mojo_module",
]

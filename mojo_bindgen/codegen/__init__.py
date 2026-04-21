"""Public Mojo code generation API.

Import from this package when you want the stable, higher-level codegen
surface rather than the individual implementation modules.
"""

from mojo_bindgen.codegen.generator import MojoGenerator, generate_mojo
from mojo_bindgen.codegen.mojo_emit_options import FFIScalarStyle, MojoEmitOptions
from mojo_bindgen.codegen.mojo_ir_printer import (
    MojoIRPrinter,
    MojoIRPrintOptions,
    render_mojo_module,
)

__all__ = [
    "FFIScalarStyle",
    "MojoIRPrinter",
    "MojoIRPrintOptions",
    "MojoGenerator",
    "MojoEmitOptions",
    "generate_mojo",
    "render_mojo_module",
]

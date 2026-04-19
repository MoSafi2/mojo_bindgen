"""Public Mojo code generation API.

Import from this package when you want the stable, higher-level codegen
surface rather than the individual implementation modules.
"""

from mojo_bindgen.codegen.generator import MojoGenerator, generate_mojo
from mojo_bindgen.codegen.mojo_emit_options import FFIScalarStyle, MojoEmitOptions

__all__ = [
    "FFIScalarStyle",
    "MojoGenerator",
    "MojoEmitOptions",
    "generate_mojo",
]

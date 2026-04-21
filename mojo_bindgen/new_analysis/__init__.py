"""New MojoIR-oriented analysis pipeline components.

This package is intentionally separate from :mod:`mojo_bindgen.analysis` while
the new CIR -> MojoIR pipeline is still being built out.
"""

from mojo_bindgen.new_analysis.type_lowering import (
    LowerTypePass,
    TypeLoweringError,
    lower_type,
)

__all__ = [
    "LowerTypePass",
    "TypeLoweringError",
    "lower_type",
]

"""New MojoIR-oriented analysis pipeline components.

This package is intentionally separate from :mod:`mojo_bindgen.analysis` while
the new CIR -> MojoIR pipeline is still being built out.
"""

from mojo_bindgen.new_analysis.const_lowering import (
    ConstExprLoweringError,
    LowerConstExprPass,
    lower_const_expr,
)
from mojo_bindgen.new_analysis.decl_lowerer import UnitLoweringError
from mojo_bindgen.new_analysis.struct_lowering import (
    LowerStructPass,
    StructLoweringError,
    lower_struct,
)
from mojo_bindgen.new_analysis.type_lowering import (
    LowerTypePass,
    TypeLoweringError,
    lower_type,
)
from mojo_bindgen.new_analysis.union_lowering import (
    LowerUnionPass,
    UnionLoweringError,
    lower_union,
)
from mojo_bindgen.new_analysis.unit_lowering import (
    LowerUnitPass,
    lower_unit,
)

__all__ = [
    "ConstExprLoweringError",
    "LowerConstExprPass",
    "LowerStructPass",
    "LowerTypePass",
    "LowerUnionPass",
    "LowerUnitPass",
    "StructLoweringError",
    "TypeLoweringError",
    "UnionLoweringError",
    "UnitLoweringError",
    "lower_const_expr",
    "lower_struct",
    "lower_type",
    "lower_union",
    "lower_unit",
]

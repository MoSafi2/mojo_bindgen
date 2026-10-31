"""Native Mojo bindgen library. The first slice provides recursive type mapping."""

from .ir import CType, MojoType, TargetABI
from .type_mapping import MapTypePass, TargetQueries, map_type, validate_type_tree

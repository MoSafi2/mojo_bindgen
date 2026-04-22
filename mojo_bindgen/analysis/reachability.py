"""Compatibility re-export for the active reachability pass implementation."""

from mojo_bindgen.new_analysis.reachability import (
    ReachabilityMaterializePass,
    ReachabilityMaterializeResult,
    ReachabilityOptions,
    materialize_reachable_struct_refs,
)

__all__ = [
    "ReachabilityMaterializePass",
    "ReachabilityMaterializeResult",
    "ReachabilityOptions",
    "materialize_reachable_struct_refs",
]

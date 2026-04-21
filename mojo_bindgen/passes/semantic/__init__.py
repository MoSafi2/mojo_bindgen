"""Backend-neutral semantic helpers and passes."""

from mojo_bindgen.passes.semantic.callbacks import (
    CallbackAlias,
    CallbackAliasInfo,
    CollectCallbackAliasesPass,
    collect_callback_aliases,
)
from mojo_bindgen.passes.semantic.imports import (
    CollectSemanticNeedsPass,
    ImportNeeds,
    collect_unit_import_and_fallback_needs,
)
from mojo_bindgen.passes.semantic.layout import (
    ComputeLayoutFactsPass,
    LayoutFacts,
    bitfield_field_is_bool,
    bitfield_field_is_signed,
    bitfield_storage_width_bits,
    build_register_passable_map,
    incomplete_struct_decls,
    is_pure_bitfield_struct,
    ordered_struct_decls,
    struct_by_decl_id,
    struct_decl_register_passable,
)
from mojo_bindgen.passes.semantic.names import (
    CollectEmissionNamesPass,
    EmissionNameFacts,
    emitted_struct_enum_names,
    emitted_typedef_mojo_names,
)
from mojo_bindgen.passes.semantic.type_walk import TypeWalkOptions, any_type_node, collect_type_nodes, iter_type_nodes

__all__ = [
    "CallbackAlias",
    "CallbackAliasInfo",
    "CollectCallbackAliasesPass",
    "CollectEmissionNamesPass",
    "CollectSemanticNeedsPass",
    "ComputeLayoutFactsPass",
    "EmissionNameFacts",
    "ImportNeeds",
    "LayoutFacts",
    "TypeWalkOptions",
    "any_type_node",
    "bitfield_field_is_bool",
    "bitfield_field_is_signed",
    "bitfield_storage_width_bits",
    "build_register_passable_map",
    "collect_callback_aliases",
    "collect_type_nodes",
    "collect_unit_import_and_fallback_needs",
    "emitted_struct_enum_names",
    "emitted_typedef_mojo_names",
    "incomplete_struct_decls",
    "is_pure_bitfield_struct",
    "iter_type_nodes",
    "ordered_struct_decls",
    "struct_by_decl_id",
    "struct_decl_register_passable",
]

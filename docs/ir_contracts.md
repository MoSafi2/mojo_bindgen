# Recursive IR contracts

`mojo_bindgen.ir` is the schema import surface. The production pipeline retains
the parser → CIR analysis → Mojo mapping → target normalization → printing layers.

The Python-specific dataclass, tuple and Pyright details below describe the
reference in `legacy/python/`. Production Mojo uses recursive payload enums,
standard `ArcPointer` children, borrowed passes and an immutable publication
contract. Its `mojo_bindgen.ir` and `serde` APIs expose the corresponding schemas
and free debug codecs; see [the Mojo guide](../mojo/README.md).

## Stages and publication

`CType` and `CConstExpr` are closed source families. `MojoType` and
`MojoConstExpr` are closed target families. Recursive containers and expression
operators have distinct `C` and `Mojo` payloads, including callback parameters,
casts, calls, references, and `sizeof`. Integer, string, and character literals
are shared immutable data. `CFloatLiteral.spelling` preserves source text;
`MojoFloatLiteral.value` is numeric.

Every published IR dataclass is frozen, and child collections are tuples.
Mutable lists belong to parser construction and pass-local output accumulation.
Passes return replacements without modifying their inputs. Named declaration
references carry stable symbol keys and geometry; they do not own record fields.
Shared acyclic children and nominal record recursion are valid. Structural type
cycles are rejected before analysis, independently of traversal filtering.

`RecordRegistry` distinguishes declared, building, and completed records. A
building header exposes naming and geometry for references, while completed
records alone are available through definition lookup. Failed construction
restores the prior state. Incomplete forward declarations are valid CIR records.

## Mapping and dispatch

Type lowering returns `CType`. `MapTypePass(queries=...)` accepts source types and
returns `MojoType`; its target queries are fixed and it retains no mapping results.
`MapConstExprPass` accepts `CConstExpr` and returns `MojoConstExpr`. Normalization
and printing accept target families only. Closed dispatch ends in `assert_never`
so adding a variant requires updating consumers under Pyright.

`AnalysisContext` caches declaration/layout facts by stable symbol keys for one
immutable source unit. `MappingSession` binds that unit, target queries through
its mapper, options, and collaborators for a run. Per-run output state is discarded
on failure. Union-arm deduplication compares mapped types structurally in encounter
order, preserving the first arm and diagnostic order.

`DeclLowerer.lower_top_level_decl` returns `tuple[Decl, ...]` and
`UnitDeclMapper.map_decl` returns `tuple[MojoDecl, ...]` for zero, one, or many
outputs. Private leaf helpers may return optional values.

## Debug serialization

IR payloads have no serialization methods. Use the free functions in
`mojo_bindgen.serde`:

- CIR: `encode_cir` / `decode_cir`, `dumps_cir` / `loads_cir`.
- MojoIR: `encode_mojo_ir` / `decode_mojo_ir`, `dumps_mojo_ir` / `loads_mojo_ir`.
- Nodes: `to_debug_dict`, `decode_node`, and stage-specific
  `decode_c_type`, `decode_mojo_type`, `decode_c_expr`, `decode_mojo_expr`.

Each dataclass encodes as `{"kind": "ConcreteClassName", "fields": {...}}`.
The `fields` object includes every declared field, including defaults and `null`.
This envelope also preserves payload fields named `kind`. Enums encode by value;
tuples encode as JSON arrays and are reconstructed as tuples. Explicit family
registries reject unknown tags and wrong-stage recursive payloads. Omitted fields
use normal constructor defaults; unknown fields fail.

This is an unversioned debug/test representation kept in sync with code, with no
migrations, legacy decoders, or stable wire tags. The CLI flags `--dump-cir`
and `--dump-mojo-ir` retain their names. Diagnostic JSON has a separate,
unchanged contract. Binding and layout-test output is unchanged by this refactor.

# Analysis Architecture

`mojo_bindgen.analysis` is the post-parse decision layer between normalized IR and rendering.

It answers questions like:

- which structs are representable as typed fieldwise Mojo records
- where exact-layout padding must be synthesized
- when a record must fall back to opaque byte storage
- which unions can be emitted as `UnsafeUnion`
- which callbacks, imports, and wrapper forms the generated module needs

## Package Shape

The package is intentionally flat:

- [`analysis/analyze_for_mojo.py`](../mojo_bindgen/analysis/analyze_for_mojo.py)
  Top-level orchestration for semantic analysis. Builds shared facts, runs the specialized analyzers, and assembles `AnalyzedUnit`.
- [`analysis/model.py`](../mojo_bindgen/analysis/model.py)
  Typed analyzed model consumed by rendering.
- [`analysis/struct_analysis.py`](../mojo_bindgen/analysis/struct_analysis.py)
  Struct lowering and record-layout representability checks.
- [`analysis/union_analysis.py`](../mojo_bindgen/analysis/union_analysis.py)
  Union lowering decisions.
- [`analysis/tail_decl_analysis.py`](../mojo_bindgen/analysis/tail_decl_analysis.py)
  Non-struct declaration analysis for typedefs, enums, functions, globals, constants, and macros.
- [`analysis/layout.py`](../mojo_bindgen/analysis/layout.py)
  Backend-neutral layout facts and register-passability helpers.
- [`analysis/callbacks.py`](../mojo_bindgen/analysis/callbacks.py)
  Callback alias discovery and bookkeeping.
- [`analysis/imports.py`](../mojo_bindgen/analysis/imports.py)
  Semantic import requirement discovery.
- [`analysis/names.py`](../mojo_bindgen/analysis/names.py)
  Emission-name collection and collision handling.
- [`analysis/type_walk.py`](../mojo_bindgen/analysis/type_walk.py)
  Reusable type-tree traversal helpers.
- [`analysis/pipeline.py`](../mojo_bindgen/analysis/pipeline.py)
  IR-to-IR normalization pipeline entry point.
- [`analysis/reachability.py`](../mojo_bindgen/analysis/reachability.py)
  Reachability materialization for referenced structs.
- [`analysis/validate_ir.py`](../mojo_bindgen/analysis/validate_ir.py)
  IR validation.
- [`analysis/common.py`](../mojo_bindgen/analysis/common.py)
  Small shared helpers used by the split analyzers.

## Flow

`Unit`
-> `analysis.pipeline.run_ir_passes()`
-> `analysis.analyze_for_mojo.analyze_unit_semantics()`
-> `AnalyzedUnit`
-> `codegen.render.MojoRenderer`
-> Mojo source

## Responsibilities

### IR pipeline

The pipeline modules transform or validate IR without making Mojo-specific presentation decisions.

- `validate_ir` checks internal consistency.
- `reachability` ensures referenced structs are materialized.
- `pipeline` defines the order.

### Shared semantic facts

Several flat modules compute reusable facts before declaration-specific lowering:

- `layout` computes struct maps, ordering, and register-passability facts.
- `names` determines what names are already claimed.
- `callbacks` identifies callback aliases that need stable surfaced names.
- `imports` records semantic import needs and fallback notes.

### Declaration analysis

The split declaration analyzers consume the shared facts and produce render-ready decisions:

- `struct_analysis` owns record ABI/layout representability.
- `union_analysis` owns union lowering strategy.
- `tail_decl_analysis` owns the rest of the declaration kinds.

`analyze_for_mojo` coordinates them and assembles `AnalyzedUnit`.

## Design Rules

- IR stores facts that are true about the parsed C API.
- Analysis stores decisions that depend on Mojo representability or emission policy.
- Rendering should follow analyzed decisions mechanically and should not re-decide ABI policy.
- Layout checks for records belong in `struct_analysis`, not in rendering.

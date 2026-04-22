# CIR Pass Workflow

This document shows the current CIR-to-CIR pass pipeline and where it sits
between parsing and later Mojo-facing lowering.

## Overview

```mermaid
flowchart TD
    A[raw parser Unit] --> B[analysis.AnalysisOrchestrator]
    B --> C[run_ir_passes]
    C --> D[ValidateIRPass]
    D --> E{IR invariants hold?}
    E -->|no| F[IRValidationError]
    E -->|yes| G[ReachabilityMaterializePass]
    G --> H[prepend synthesized incomplete Structs for orphan StructRefs]
    H --> I[analysis.lower_unit]
    I --> J[MojoModule]
    J --> K[assign_record_policies]
    K --> L[normalize_mojo_module]
    L --> M[printer-ready MojoModule]
```

## Active Passes

The current `run_ir_passes()` implementation is short and explicit, but it now
belongs to the analysis orchestrator boundary rather than a standalone
integration module:

1. `ValidateIRPass`
2. `ReachabilityMaterializePass`

Source:
- [orchestrator.py](/home/mohamed/Documents/Projects/mojo_bindgen/mojo_bindgen/analysis/orchestrator.py:15)

## Pass Details

### `ValidateIRPass`

Purpose:
- verify `decl_id` uniqueness across the `Unit`
- require `decl_id` on typedefs and structs
- verify nested type references are structurally valid
- reject malformed `TypeRef`, `StructRef`, and `OpaqueRecordRef` nodes that
  lack identity

This is a fail-fast structural correctness gate. It does not rewrite the IR.

Source:
- [validate_ir.py](/home/mohamed/Documents/Projects/mojo_bindgen/mojo_bindgen/analysis/validate_ir.py:17)

### `ReachabilityMaterializePass`

Purpose:
- walk all reachable CIR types and selected const-expression type positions
- collect orphan `StructRef` uses that have no top-level `Struct` declaration
- prepend synthesized incomplete `Struct` declarations for those refs

This ensures downstream consumers can emit opaque struct stubs for external or
indirectly referenced record types.

Source:
- [reachability.py](/home/mohamed/Documents/Projects/mojo_bindgen/mojo_bindgen/analysis/reachability.py:153)

## Why These Passes Exist

The parser is intentionally source-driven and local. That means it can produce
valid-looking references to records that never appeared as top-level
declarations in the primary header. `ReachabilityMaterializePass` repairs that
for global downstream consistency.

`ValidateIRPass` comes first so the reachability walk only runs over structurally
sound CIR.

## What Comes Next

After the CIR pass sequence, analysis continues with Mojo-facing lowering and
finalization:

- `analysis.lower_unit`: CIR -> MojoIR
- `assign_record_policies`: derive struct traits and fieldwise-init eligibility
- `normalize_mojo_module`: MojoIR -> printer-ready MojoIR

So the CIR pass layer is intentionally narrow inside a broader orchestrated
analysis flow: validate first, then materialize reachable opaque records, then
hand off to MojoIR lowering.

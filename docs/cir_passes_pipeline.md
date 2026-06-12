# Analysis Pass Pipeline

This is the main reference for analysis-owned passes in `mojo-bindgen`.
Analysis starts with a raw parser `Unit`, validates and normalizes CIR, computes
shared facts, lowers into policy-light MojoIR, and assigns late Mojo record
policies.

`NormalizeMojoModulePass` is intentionally not documented here in detail. It is
codegen-facing and has its own reference:
[mojo_ir_normalization_pipeline.md](mojo_ir_normalization_pipeline.md).

## Overview

```mermaid
flowchart TD
    A[raw parser Unit] --> B[ValidateIRPass]
    B --> C[SignatureRecordStubPass]
    C --> D[CIRCanonicalizer]
    D --> E[ValidateIRPass]
    E --> F[ValidateReferencesPass]
    F --> G[build_analysis_context]

    G --> H[declaration indexes]
    G --> I[DeclDependencyGraph]
    G --> J[AliasClassification]
    G --> K[RecordLayoutFacts]
    G --> L[RecordAnalysisFacts]

    G --> M[LowerUnitPass]
    M --> N[LowerTypePass]
    M --> O[LowerConstExprPass]
    M --> P[UnitDeclLowerer]
    P --> Q[struct_lowering]
    P --> R[LowerUnionPass]

    M --> S[policy-light MojoModule]
    S --> T[PolicyInferencePass]
    T --> U[policy-final MojoModule]
    U --> V[NormalizeMojoModulePass in codegen docs]
```

The compatibility entry points are:

- `run_ir_passes(unit)`: validates and normalizes CIR.
- `lower_unit(unit)`: lowers normalized CIR, building fallback context if needed.
- `AnalysisOrchestrator.analyze_with_artifacts(unit)`: returns the stable public
  `AnalysisResult`.
- `AnalysisOrchestrator.analyze_pipeline(unit)`: returns `AnalysisArtifacts`
  with normalized CIR, `AnalysisContext`, policy-light MojoIR, and final MojoIR.

## Stage 1: CIR Validation And Normalization

These passes operate on C-facing IR (`Unit`) and must not depend on MojoIR.

### `ValidateIRPass`

Purpose:

- verify stable declaration identity where downstream passes require it
- reject conflicting duplicate `decl_id` values
- require `decl_id` on `Typedef`, `Struct`, `TypeRef`, `StructRef`, and
  `OpaqueRecordRef` positions that participate in cross-reference analysis

Placement:

- runs first on raw parser CIR
- runs again after CIR repair/canonicalization

It does not prove ABI representability or reference reachability. Those are
owned by later analysis passes.

### `SignatureRecordStubPass`

Purpose:

- walk reachable type positions in functions, typedefs, records, globals,
  constants, and macros
- optionally walk const-expression type positions
- synthesize incomplete `Struct` declarations for signature-only `StructRef`
  uses that have no top-level record declaration

This keeps signatures such as `int f(struct opaque *p);` lowerable as opaque
Mojo record stubs.

### `CIRCanonicalizer`

Purpose:

- keep one record declaration per `decl_id`, preferring complete definitions
- deduplicate equivalent function declarations
- keep the last definition for repeated macro names
- drop self-alias macros already represented by constants or enumerants
- choose enum primary names from typedef/tag information
- rewrite enum references to the chosen primary names

The canonicalizer returns a fresh `Unit`; callers should not rely on mutation of
the raw parser result.

### `ValidateReferencesPass`

Purpose:

- reject normalized CIR references that should resolve but do not
- require `EnumRef` declarations to exist in the normalized `Unit`
- require concrete non-union `StructRef` declarations to exist after signature
  stub materialization
- allow external typedef references, because `LowerUnitPass` can synthesize
  external typedef aliases
- allow `OpaqueRecordRef` to remain opaque/external

This is the dangling-reference gate for normalized CIR.

## Stage 2: Shared Analysis Context

`build_analysis_context(unit)` computes reusable whole-unit facts after CIR is
normalized and reference-validated. This stage should absorb analysis work that
would otherwise be repeated inside lowerers.

### Declaration Indexes

`AnalysisContext` indexes normalized declarations by stable keys:

- records by `decl_id`
- typedefs by `decl_id`
- enums by `decl_id`
- functions by `decl_id`
- globals by `decl_id`
- constants by name
- macros by name

These indexes are the basic lookup surface for later passes.

### `DeclDependencyGraph`

Purpose:

- record type-reference edges from declarations to typedefs, records, and enums
- record symbol-reference edges from constant expressions and macros
- provide a foundation for diagnostics, stable ordering, and future
  allowlist/pruning support

This pass is fact-building only; it does not reorder or delete declarations.

### `AliasClassification`

Purpose:

- classify local typedef declarations
- classify external typedef references found in type positions
- identify callback typedefs, enum aliases, record aliases, exact-width stdint
  aliases, ordinary typedefs, and external typedefs

This keeps alias meaning available as shared facts instead of rediscovering it
inside lowerers.

### `RecordLayoutFacts`

Purpose:

- analyze physical record layout from CIR offsets/sizes
- compute plain field facts, bitfield storage runs, padding spans, natural typed
  alignment, and layout problems
- preserve incomplete-record facts without forcing a lowering decision

`analyze_record_layout()` owns pure C-layout checks. It does not decide how a
Mojo `StructDecl` should be emitted.

### `RecordAnalysisFacts` / `RecordShapeAnalyzer`

Purpose:

- centralize record shape and representability decisions
- classify record storage as incomplete, union, typed, or opaque storage
- validate direct and embedded flexible-tail patterns
- analyze recursive by-value record shapes
- carry flexible-tail metadata for struct lowering
- carry fallback reasons for opaque-storage diagnostics

This is the central record analysis pass. `struct_lowering` consumes these facts
and performs MojoIR member construction; it should not own recursive record
shape policy.

## Stage 3: CIR To MojoIR Lowering

Lowering consumes normalized CIR plus `AnalysisContext` and produces a
policy-light `MojoModule`. These passes are Mojo-facing, but still live in
analysis because they convert analyzed CIR into MojoIR.

### `LowerUnitPass`

Purpose:

- create shared lowerers for one unit
- synthesize aliases for external typedef references when needed
- lower top-level declarations through `UnitDeclLowerer`
- build module metadata and linking mode

`lower_unit(unit)` remains a compatibility helper. If no `AnalysisContext` is
provided, it builds one internally.

### `UnitDeclLowerer`

Purpose:

- dispatch each top-level CIR declaration to the correct lowerer
- lower typedefs, enums, functions, globals, constants, macros, structs, and
  unions
- preserve declaration order except for intentionally synthesized aliases

This is orchestration, not whole-unit analysis. New cross-declaration facts
should generally be added to `AnalysisContext`.

### `LowerTypePass`

Purpose:

- map CIR types to MojoIR type nodes
- preserve named typedef/record/enum surfaces as `NamedType`
- lower pointers, arrays, function pointers, atomics, vectors, complex values,
  and unsupported sized types

This is a recursive type lowerer. It does not decide declaration reachability or
record storage policy.

### `LowerConstExprPass`

Purpose:

- lower CIR constant-expression nodes to MojoIR constant-expression nodes
- lower cast and `sizeof` target types through `LowerTypePass`
- reject constant forms that have no direct MojoIR value form, such as null
  pointer literals

Macro emission policy lives in `UnitDeclLowerer`; expression lowering only
rewrites supported expression shapes.

### Struct Lowering

Purpose:

- consume `RecordAnalysisFacts` and `RecordLayoutFacts`
- emit opaque declarations for incomplete records
- emit byte-storage structs for opaque-storage decisions
- lower typed plain fields and bitfield groups to MojoIR members
- attach flexible-tail metadata computed by record analysis
- compute Mojo alignment decorator policy

Struct lowering should not recompute recursive record shape decisions.

### `LowerUnionPass`

Purpose:

- lower complete unions to `UnsafeUnion[...]` when member types are distinct and
  representable
- fall back to `InlineArray[UInt8, size]` when union lowering would be unsafe or
  ambiguous
- emit placeholder aliases for incomplete unions

Union lowering remains separate because unions lower to alias-style layout
types, not `StructDecl`.

## Stage 4: Late MojoIR Policy Analysis

### `PolicyInferencePass`

Purpose:

- infer record passability
- assign Mojo traits
- decide fieldwise initializer eligibility
- handle recursion, opaque storage, arrays, atomics, pointers, aliases, and
  nested records

This pass runs after CIR-to-MojoIR lowering because it reasons over final MojoIR
types and declaration relationships.

## Codegen Boundary

After `PolicyInferencePass`, analysis hands a policy-final `MojoModule` to
codegen. `NormalizeMojoModulePass` then makes printer-facing facts explicit:
callback alias hoisting, imports, support declarations, final call targets, and
nested type normalization.

That codegen-facing pass is documented separately in
[mojo_ir_normalization_pipeline.md](mojo_ir_normalization_pipeline.md).

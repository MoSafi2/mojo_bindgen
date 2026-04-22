# Parsing Pipeline: C Source to CIR

This document shows the current parser path from a C header on disk to the
raw CIR `Unit` returned by `ClangParser.run()`. Analysis-owned passes start
only after this hand-off.

## Overview

```mermaid
flowchart TD
    A[C header path + compile args] --> B[ClangParser]
    B --> C[_resolve_header_path]
    C --> D[ClangFrontendConfig]
    D --> E[ClangFrontend.parse_translation_unit]
    E --> F[libclang TranslationUnit]

    F --> G[collect_diagnostics]
    G --> H[ParserDiagnosticSink]

    F --> I[RecordRegistry.build_from_translation_unit]
    I --> J[Record definition index + stable decl IDs]

    J --> K[TypeLowerer]
    J --> L[RecordLowerer]
    K --> M[DeclLowerer]
    L --> M
    F --> M

    M --> N[Functions / typedefs / enums / globals]
    M --> O[RecordLowerer.lower_top_level_record]
    M --> P[ConstExprParser + macro collection]

    O --> Q[Struct / union IR]
    N --> R[Other top-level CIR decls]
    P --> S[Const / MacroDecl IR]

    Q --> T[raw Unit]
    R --> T
    S --> T
    H --> T

    T --> U[raw CIR Unit]
```

## Stage Boundaries

### 1. Frontend setup

`ClangParser._build_parser_session()` creates the frontend boundary:
- resolves the header path
- computes effective compile arguments
- asks libclang to parse one translation unit
- collects frontend diagnostics
- builds a `RecordRegistry` for stable record identity and lookup

This stage is in:
- [parser.py](/home/mohamed/Documents/Projects/mojo_bindgen/mojo_bindgen/parsing/parser.py:66)
- [frontend.py](/home/mohamed/Documents/Projects/mojo_bindgen/mojo_bindgen/parsing/frontend.py:92)
- [registry.py](/home/mohamed/Documents/Projects/mojo_bindgen/mojo_bindgen/parsing/registry.py:86)

### 2. Raw declaration lowering

`DeclLowerer` walks top-level primary-file cursors and delegates by declaration
family:
- functions, typedefs, enums, globals: lowered directly by `DeclLowerer`
- structs/unions: delegated to `RecordLowerer`
- macros: collected after cursor traversal

This stage is intentionally source-faithful. It does not do post-parse semantic
repair.

Key modules:
- [decl_lowering.py](/home/mohamed/Documents/Projects/mojo_bindgen/mojo_bindgen/parsing/lowering/decl_lowering.py:31)
- [record_lowering.py](/home/mohamed/Documents/Projects/mojo_bindgen/mojo_bindgen/parsing/lowering/record_lowering.py:205)
- [type_lowering.py](/home/mohamed/Documents/Projects/mojo_bindgen/mojo_bindgen/parsing/lowering/type_lowering.py:71)

### 3. Record-specific lowering

`RecordLowerer` owns physical field discovery and record materialization:
- discovers normalized field sites, including direct anonymous record members
- preserves Clang byte offsets and bitfield offsets
- lowers nested inline records exactly once through the registry cache
- emits incomplete `Struct` rows for forward declarations when needed

The output here is still raw CIR `Struct` data, not a Mojo-facing layout plan.

### 4. Unit assembly

`ClangParser.run_raw()` assembles:
- `source_header`
- `library`
- `link_name`
- raw lowered `decls`
- parser diagnostics converted to IR diagnostics

This produces a source-faithful but not yet normalized `Unit`.

### 5. Hand-off boundary

`ClangParser.run()` stops at raw CIR. Any later CIR normalization or lowering
belongs to the analysis layer, not the parser. In the current code shape that
means `AnalysisOrchestrator` owns:

- CIR validation
- reachability materialization
- CIR -> MojoIR lowering
- late record policy assignment
- MojoIR normalization

## Output Shapes

There are two useful checkpoints:

| Entry point | Output |
| --- | --- |
| `ClangParser.run_raw()` | raw source-faithful CIR `Unit` |
| `ClangParser.run()` | raw source-faithful CIR `Unit` |

Both entry points now expose the parser boundary before analysis-owned CIR
repair.

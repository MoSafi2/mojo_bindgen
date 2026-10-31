# Python refactor for the recursive Mojo rewrite

Agreed implementation contract, replacing the earlier compatibility/caching draft.
The Python implementation now uses this model; integration evidence is recorded
below. Historical experiments and future Mojo sources remain in
[the results ledger](mojo_rewrite_results.md), which is preserved unchanged.

## Objective and fixed decisions

Make the eventual Mojo rewrite primarily a translation of closed dataclass variants
into enum payloads and Python references into standard smart pointers. Preserve
existing binding algorithms, naming, Unicode handling, qualifiers, callback
conventions, arithmetic, layout decisions, flexible/zero-length array policies,
link modes, diagnostic JSON, and top-level bindgen/options/orchestrator/results APIs.

- Recursive types with named declaration references; no flat type-node storage.
- Separate CIR and MojoIR type and expression families, including nested payloads.
- Immutable published IR, with mutable construction kept private.
- Pure type mapping without result memoization, interning, or structural caches.
- Unversioned debug/test IR JSON changes with the implementation. No migrations,
  legacy omission specifications, decoder shims, or compatibility constructors.
- Keep `Unit`, `MojoModule`, parser/analysis/codegen layers, `AnalysisContext`,
  `MappingSession`, and `ir.py` as the schema import surface.
- No native Mojo implementation, ownership wrapper framework, generic visitor,
  type erasure, or restored experiments in this refactor.

## 1. Replace mixed schemas and wire all consumers

Implemented in [ir.py](../mojo_bindgen/ir.py), parser lowering, fact analysis,
CIR canonicalization, mapping, target normalization, and printing.

- Closed `CType`/`MojoType` families use `CPointer`/`MojoPointer`,
  `CArray`/`MojoArray`, `CFunctionPtr`/`MojoFunctionPtr`, and `CParam`/`MojoParam`.
  Source payloads retain qualifiers, array shapes, conventions, and ABI geometry;
  target payloads contain mapped types, fixed array sizes, pointer policies, and
  emitted callback attributes. Target members and `TypeArg` accept only `MojoType`.
- Closed `CConstExpr`/`MojoConstExpr` families split recursive operators,
  references, casts, calls, and `sizeof`. Source floats retain spelling; target
  floats contain numeric values. Integer/string/character data is shared immutable
  payload data. Null pointer literals remain source-only.
- Lowering returns source families. Mapping returns target families. Normalization
  and printing accept only target families. The mixed `Type`, `ConstExpr`, shared
  container APIs, and mixed decoder helpers have been removed directly.

## 2. Make serialization a debug-only boundary

Implemented in [serde.py](../mojo_bindgen/serde.py), CLI debug dumps, active
roundtrip tests, and deliberately updated corpus IR JSON expectations.

- Free CIR/MojoIR encode/decode/dump/load functions replace payload serialization
  methods and `SerDeMixin`. Explicit family registries select current concrete
  classes; ordinary field reflection stays inside serialization.
- Dataclasses encode as `{"kind": "ConcreteClassName", "fields": {...}}`, retaining
  all fields including defaults and `None`. The envelope handles payloads with
  their own `kind` field. Enums encode by value and tuples as JSON arrays.
- Decoders reconstruct tuples, apply normal constructor defaults, and reject
  unknown tags, unknown fields, missing required fields, and wrong-stage children.
  There is no owner-module inference, alias-name inference, version field, or
  legacy decoder. Keep snapshots synchronized with schema changes.
- Union-arm deduplication uses ordered typed structural equality, preserving the
  first mapped arm and diagnostic ordering. It does not use serialization.
- `--dump-cir`, `--dump-mojo-ir`, and diagnostic JSON retain their CLI contracts.

## 3. Separate construction from immutable publication

Implemented in [registry.py](../mojo_bindgen/parsing/registry.py),
[record_lowering.py](../mojo_bindgen/parsing/lowering/record_lowering.py), parser
accumulation, and frozen schema payloads.

- Published types, expressions, declarations, dependencies, and root IR objects are
  frozen dataclasses with tuple-valued children. Builders and pass-local output
  accumulators retain mutable lists; publication snapshots them into tuples.
- Registry states distinguish declared, building, and completed records. Building
  headers expose names and geometry for nominal references without exposing
  unfinished definitions. Valid incomplete forward declarations are separate IR.
- Failure discards unfinished state and restores any prior declaration, leaving
  previously published records unchanged. Canonicalization and normalization
  construct replacement results. Python references provide sharing directly.

## 4. Make mapping pure and context-bound

Implemented in [type_mapping.py](../mojo_bindgen/analysis/mojo/type_mapping.py),
[type_walk.py](../mojo_bindgen/analysis/type_walk.py), validation, context/session
construction, and local mapping accumulation.

- `MapTypePass` requires explicit, fixed `TargetQueries`. It has no result cache,
  active-ID cache, memoization, or interning. Standalone helpers also require an
  explicit mapping collaborator or queries.
- `AnalysisContext` belongs to an immutable source unit; declaration/layout facts
  remain cached by stable symbol keys. A context supplied for another unit is
  rebuilt for that unit. Each mapping run constructs its session and outputs.
- Structural cycle validation follows all owning type edges independently of
  filtered traversal options, before analysis. Shared acyclic children and
  nominal recursive records remain valid. Mapping errors retain no partial result
  state. Canonicalizer record lookup is local to each invocation.

## 5. Close dispatch and standardize pass results

Implemented across family transformers/walkers, declaration dispatch,
normalization, record policies, printing, and typed layout/storage helpers.

- Use closed union narrowing and `assert_never` for exhaustive transformations.
  Core arguments have stage-specific types; there are no core `Any`/cast escape
  hatches hiding stage violations. Libclang compatibility remains at the frontend
  boundary; reflection remains at the debug codec boundary.
- Public declaration lowering always returns `tuple[Decl, ...]`; public declaration
  mapping always returns `tuple[MojoDecl, ...]`. Orchestration extends these tuples
  without branches for `None`, singleton, or list results. Private leaf helpers may
  retain optional results.
- Expansion order, duplicate policies, diagnostics, and traversal options remain
  unchanged. No generic visitor/type-erasure framework was introduced.

## 6. Integration, documentation, and acceptance

The [IR contract reference](../docs/ir_contracts.md) documents the production model,
ownership, fixed mapping contexts, and current debug JSON format. The historical
results ledger remains intact and no experiment code has been recreated.

Required checks:

- Focused source/target schema, expression, ownership, registry recovery, mapping,
  cycle validation, CLI debug dump, and serialization tests.
- `pixi run --locked check-light`: formatting, Ruff, Pyright, and light tests.
- `pixi run --locked test`: full suite including native compilation/runtime tests.
- Compare binding and layout output in both link modes with the pre-refactor
  baseline. JSON expectations change deliberately; generated Mojo goldens do not.

Acceptance requires one recursive production model per stage, immutable published IR,
identity-independent mapping, explicit pass contracts, active serialization tests,
and unchanged generated binding/layout output. Missing toolchains/platforms must
be reported as unverified scope; host Linux checks do not establish other hosts.


### Final integration evidence (2026-10-31)

- `pixi run --locked check-light`: passed formatting, Ruff, and Pyright (zero
  errors), plus **396 passed, 26 deselected** light tests.
- `pixi run --locked test`: **422 passed, no skips** on host Linux with Python
  3.14.6 and Mojo 1.2.0 (`2016d0cd`). This includes all 26 native compilation and
  runtime cases, with existing negative compilation expectations preserved.
- Compared pre-refactor and final binding/layout source for 49 headers in both
  `external_call` and `owned_dl_handle` modes: **all 98 cases identical**, covering
  196 rendered artifacts. Existing generated Mojo goldens remain unchanged.
- A temporary negative Pyright probe rejected all eight deliberate stage
  violations: nested arrays in both directions, a target type argument, casts in
  both directions, callback parameters, type mapper input, and expression mapper
  input. No probe or experiment package was added to the repository.
- Active C/Mojo roundtrips cover current schemas, tuple reconstruction, defaults,
  unknown tags/fields, wrong-stage children, and real CLI debug sidecars. The old
  blanket MojoIR serialization skip is removed.
- Ownership/recovery checks cover sealed parser/analysis results, shared children,
  nominal recursion, cyclic owning edges, forward/builder rollback, independent
  contexts and units, atomic publication of facts, and failed declarations leaving
  emitted-constant lookup unchanged before a successful retry.
- `git diff --check` passed. The historical experiment ledger, dependency pins,
  and generated Mojo files are unchanged. Validation covers the host Linux
  toolchain; other host platforms were not exercised.

# Slice 2: complete native backend

The native generator and Python reference coexist in this repository. This slice
adds generation from constructed CIR. Native parsing, command-line compatibility,
libclang integration, wrapper transition, and publishing remain stages 3–5 of
[native_mojo_roadmap.md](native_mojo_roadmap.md). Preserve the completed Python
refactor plan and historical results ledger.

## Package organization

Mirror Python's backend boundaries and meaningful filenames under
`mojo/mojo_bindgen/`:

- `ir.mojo`: distinct recursive CIR and MojoIR types, expressions, declarations,
  roots, diagnostics, dependencies, and record policies.
- `serde.mojo`: explicit current-model stage codecs; JSON is unversioned debug/test
  data, synchronized with both models. No runtime Python, reflection-based node
  dispatch, migrations, or legacy adapters.
- `analysis/cir/`: structural validation, reference validation, signature record
  stubs, canonicalization, and enum-reference rewriting.
- `analysis/facts/`: target queries, declaration indexes, dependency graphs, alias
  classification, physical layout, bitfield runs, storage decisions, and a source-
  bound analysis context.
- `analysis/mojo/`: pure recursive type/expression mapping, declaration expansion,
  aliases/macros/structs/unions, and late record policies.
- `analysis/pipeline.mojo`: pass ordering and owned analysis artifacts.
- `codegen/`: callback/dependency normalization, binding printer, support templates.
- `layout_tests/generator.mojo`: stable-toolchain runtime layout checks.
- `orchestrator.mojo`: `generate_from_unit` and `BackendResult`.

The package facade reexports the public constructed-IR entry points. Production
Mojo never invokes Python. The existing Python CLI and root stable SDK remain
unchanged. Test-only JSON batch drivers live in `tests/mojo/drivers/`; native unit
and ownership tests live under `tests/mojo/unit/`; differential and stable-runtime
checks live under `tests/parity/`.

## Contracts and implementation sequence

1. Move slice-1 modules into matching Python package boundaries; keep their gates
   active while completing the model.
2. Complete all closed recursive families and explicit root/expression codecs.
   Preserve every current field, default, source qualifier, spelling and ABI fact.
   Integer literal values use canonical decimal digits without a machine-width
   cap; geometry remains checked machine `Int`. Binary64 floats preserve decimal
   and hexadecimal conversion behavior. Arithmetic expressions remain unevaluated.
3. Port CIR validation/canonicalization, then context-bound indexes and facts.
   Structural ownership cycles are rejected independently of nominal references;
   shared acyclic children and named recursive records are valid.
4. Port expression and declaration mapping with local output accumulation and
   ordered zero/one/many expansion. Reuse the pure type mapper. Union deduplication
   compares typed structure in source order, never JSON fingerprints or addresses.
5. Port record policy inference, target normalization, support templates, exact
   binding printing, and layout-test generation. `generate_from_unit` returns the
   normalized source unit, finalized target module, binding source and optional
   layout source. Inputs are borrowed; published outputs are fresh.
6. Verify full-model roundtrips, all fixture intermediates, byte-identical outputs
   in both linking modes, source/context independence, ownership and failure
   recovery at O0/O3. Run existing Python checks, compiler rejection tests, stable
   generated-code runtime tests, and installed Conda import/generation smoke tests.

## Ownership and compiler constraints

Standard `ArcPointer` holds recursive children and shared source units. Nominal
references carry declaration keys, never declaration ownership. Struct/list copies
separate builders from published snapshots; passes expose borrowed immutable views.
Mojo publication immutability is an API contract, not a frozen-field language
feature. No type-node ID store, custom ownership framework, interning, or type
mapping memoization is introduced.

Use borrowed matching. The exact pinned nightly requires `__enum` and empty
recursive destructors for lifecycle inference; the historical ledger explains the
consuming-match compiler issue. The stdlib handles UTF-8 and binary64 decimal
conversion; localized Unicode property tables preserve Python naming semantics.
A private libc `strtod` call handles hexadecimal floating literals because the
pinned stdlib decimal parser rejects that syntax. No libclang dependency is needed
for this backend slice.

## Acceptance evidence

Validated on 2026-11-01, Linux x86-64, pinned native nightly
`1.3.0.dev2026103105` and the separate root stable SDK:

- `pixi run --locked check-light`: formatting, Ruff, Pyright, and **396 light tests
  passed; 60 deselected**.
- `pixi run --locked test`: **456 passed**, including **20 backend differential/
  runtime tests** and **14 type differential/compiler-contract tests**.
- `pixi run --locked native-build` and native `format-check`: passed.
- Native `test`: all **12 ownership/publication/codec/recovery tests passed at O0
  and O3** (24 executions). Source and target structural cycles are rejected and
  deliberately injected ARC cycles are broken by the tests.
- Full intermediate and binding/layout source comparisons cover **49 headers in
  both linking modes at O0/O3** (196 fixture/mode/optimization combinations).
  Root codecs roundtrip those units/modules. Constructed cases cover independent
  ABI contexts, callbacks, recursive/forward records, enum aliasing, macros,
  documentation, Unicode, options, exact large integers, signed zero, nonfinite
  values, decimal/hex conversion, random finite binary64 values and error recovery.
- Native-generated bindings compile and execute on the stable SDK for
  `full_surface_runtime`, `large_alignment`, and `zero_length_tail_access`, in both
  linking modes and with both generator optimization levels. Sidecars run too,
  with the existing padding-index failure explicitly pinned as described below.
- The development Conda recipe rendered, built a local package, and passed CLI,
  installed-library import, exact literal, binding generation and layout generation
  smoke tests outside the checkout. Nothing was uploaded.

The existing Python implementation, root stable dependency lock, and generated goldens
remain unchanged. The previous completed Python plan and experiment results
ledger remain historical evidence. No native frontend or CLI header-generation
capability is inferred from backend parity.

## Preserved reference limitations

Stable-toolchain execution exposed two existing Python layout-test limitations;
the rewrite preserves them to retain identical generated sources:

- On this host, system `max_align_t` contains a 16-byte `long double` but its mapped
  target field is 8 bytes. Full-header parity includes this declaration. The
  runtime fixtures omit this unrelated system declaration before generation.
- `large_alignment` prints multiple scalar padding fields for one padding IR
  member. The layout-test generator counts that member as one reflected index,
  so `la_item.b.offset` reads the preceding padding field (8 instead of 16). The
  differential runtime test explicitly expects this existing sidecar failure;
  bindings themselves compile and run in both link modes.

These are coordinated future fixes to both implementations, not native parity
exemptions. Other selected sidecars execute successfully; native full-header
output remains byte-identical to Python, including these limitations.


## Real example JSON handoff

The subsequent [JSON handoff stress test](native_json_handoff.md) verifies actual
Python CLI dumps for zlib, Cairo, libpng, and SQLite. Sixteen cases cover both
link modes at O0/O3, with 32 standalone native JSON-stage handoffs, exact source
comparisons, and stable generated-binding smoke execution. Example dependencies
have their own manifest/lock; the root manifest only adds a delegating task.

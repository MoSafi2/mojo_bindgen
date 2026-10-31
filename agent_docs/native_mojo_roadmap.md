# Staged native Mojo rewrite

The Python refactor is complete. Build an independent native implementation beside
Python, keep Python as the working generator and differential reference until
parity, then switch defaults and remove Python's implementation in stages. Keep a
small generation-only Python wrapper at the end. The completed Python plan and
historical experiment ledger remain unchanged.

## Fixed architecture and repository layout

- Native code: `mojo/mojo_bindgen/`, with `mojo/main.mojo` as the CLI entry point.
  Existing Python code remains in `mojo_bindgen/`.
- Native tests: `tests/mojo/`; differential harness: `tests/parity/`. Reuse the
  existing surface/corpus/stress/runtime headers and goldens.
- Separate native manifest/lock in `mojo/`, initially pinning nightly
  `1.3.0.dev2026103105` (`dc62ab6d`), Linux x86-64. Root stable-toolchain tests
  continue independently. Compiler updates are explicit and require revalidation.
- Recursive closed payload enums, distinct CIR/MojoIR families, and named nominal
  references. No flat type-node store or numeric type handles.
- Standard ARC child sharing, unique ownership where appropriate, borrowed inputs,
  immutable publication contracts, private mutable construction, explicit mapping
  contexts, fresh outputs, and no result memoization or interning.
- Preserve algorithms, naming/Unicode behavior, ABI/layout decisions, diagnostics,
  and generated binding/layout output. No performance target or new generated
  language surface is part of the rewrite.
- IR JSON is an unversioned debug/test representation synchronized with the model.
  Neither generator calls the other in production.

## Stages and completion gates

| Stage | Deliverable | Gate |
| --- | --- | --- |
| 0: foundation | Package skeleton, exact nightly lock, build/test/format tasks, native CI, and Conda recipe | Recursive payloads, sharing, borrowed matching, destruction and exception cleanup pass at O0/O3 |
| 1: type mapper | Complete current CType/MojoType families, callback parameters, target queries, structural validation, pure mapping, type debug codecs and test driver | Current type families match Python, including nesting, arrays, qualifiers, ABI/char policies, Unicode and failure recovery |
| 2: backend | Expression/declaration/root schemas and codecs; validation/canonicalization, facts, mapping, policies, normalization, binding/layout printers | Shared fixture IR yields matching intermediate results and byte-identical rendered output in both link modes |
| 3: frontend/CLI | Direct libclang_mojo parsing, registry/lowering, macros, documentation, ABI facts and frontend compatibility | Supported header corpus runs end-to-end without the Python implementation |
| 4: previews | Installable native Conda previews, Mojo API, full differential CI, small Python wrapper API and old-API deprecation | Clean installed-package, native API/CLI, wrapper and generated-binding runtime tests pass |
| 5: cutover | Make native CLI canonical, remove Python algorithms by subsystem and keep the thin wrapper | Native execution needs no Python implementation and shared acceptance coverage remains active |

The first authorized implementation slice is stages 0–1. Do not implement later
stages or restore experiment code as part of it. The CLI skeleton must describe
its limited capability honestly and keep Python's command unchanged.

## Packaging and transition

Keep `mojo-bindgen` owned by Python during coexistence. Native development and
previews use `mojo-bindgen-mojo`; the Conda package is `mojo-bindgen-native` and
contains the executable plus the `mojo_bindgen` import package. Exact compiler
requirements protect `.mojoc` compatibility. Linux x86-64 is the initial target.

At stage 3, libclang_mojo and its shared-library shim must come from a reproducible
immutable revision validated on the selected nightly. The sibling wrapper's local
compatibility changes were uncommitted at planning time and are not a release
source. Do not vendor or silently consume that checkout.

At cutover, transfer `mojo-bindgen` to the native package and remove Python's
console entry point in the same coordinated release. Keep the native alias for
wrapper use. Preserve CLI flags, output/diagnostic semantics and exit behavior.
The final Python API takes generation options and returns generated binding source,
optional layout-test source, and diagnostics. Retire the old IR-returning and
staged orchestration APIs after the preview deprecation period. The wrapper invokes
the installed native executable and reports errors; the PyPI wrapper requires the
native package separately. Native wheels are outside this initial roadmap.

Local recipes may use checkout paths. Publishing recipes use immutable source
commits. No package uploads or default switches occur in the first slice.

## Acceptance and current implementation

Stages 0–1 now have production sources, native tests, a shared-fixture differential
harness, separate CI and local installed-package checks. Detailed usage and the
compiler/Unicode constraints are in [the native README](../mojo/README.md).

Keep the Python gate active. Require native ownership/lifecycle tests and mapping
comparisons at O0/O3, plus compiler rejection of mixed-stage types and incomplete
dispatch. Keep failed mapping reusable, inputs intact, shared DAGs valid, and nominal
recursion distinct from structural cycles. Codecs cover the complete current type
model, constructor defaults, unknown tags/fields, wrong-family nodes and Unicode.

Before cutover require full corpus parity, byte-identical binding/layout sources
in both link modes, existing stable-toolchain generated-code compilation/runtime
acceptance, installed-package checks, and wrapper error tests. Preserve the last
Python generator in Git history rather than another active reference tree.

Sources: [nightly release](https://mojolang.org/releases/nightly/),
[packaging guide](https://mojolang.org/docs/tools/packaging/),
[module/compiler compatibility](https://mojolang.org/docs/manual/packages/),
[historical results and prior art](mojo_rewrite_results.md).

## First-slice validation (2026-10-31, host Linux x86-64)

- `pixi run --locked check-light`: formatting, Ruff and Pyright passed;
  **396 passed, 37 deselected**.
- `pixi run --locked test`: **433 passed**, including existing generated-code
  compilation/runtime acceptance on the root stable compiler.
- `pixi run --locked check-native`: native formatting/build passed; all six
  ownership/lifecycle/codec tests passed at both O0 and O3; **11 differential and
  compiler-contract tests passed**.
- Mapping comparisons included 418 constructed types under six target policies
  (**2,508 cases**) and **9,890 parsed type slots across 47 headers**, per
  optimization level. Unicode comparisons cover all classification-range
  transitions and both escaped and literal UTF-8 inputs. Counts describe this
  host's included headers, not a fixed cross-platform corpus size.
- The development Conda recipe built a local package and passed its installed CLI
  and precompiled-library import/mapping tests outside the checkout. The CLI's
  inspected ELF requirements include GLIBC 2.34; the recipe declares that runtime
  minimum. Nothing was uploaded.
- The Python implementation, root stable lock, generated goldens, completed Python
  refactor plan and historical experiment ledger remain unchanged. No native C
  frontend, complete binding generator, wrapper cutover, or platform expansion is
  claimed by this slice.

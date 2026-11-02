# Native Mojo rewrite roadmap

## Current direction after the distribution decision

Stages 0–3 implement the recursive native generator. Stages 4–5 now make one
`mojo-bindgen` distribution with a Python CLI facade and a public Mojo executable
and library. This supersedes the earlier split native package/alias and proposed
Python high-level wrapper API. There is no Python generation API in the product.
The completed Python refactor plan and historical experiment ledger stay intact.

- Production implementation: `mojo/mojo_bindgen/`, entry point `mojo/main.mojo`.
- Python presentation only: `mojo_bindgen/`, Typer/Rich help/completion/diagnostics.
- Isolated previous Python implementation and pytest/parity harness:
  `legacy/python/`, retained as an opt-in reference and excluded from artifacts.
- Native TestSuite tests: `tests/mojo/`; CLI tests: `tests/cli/`; shared headers,
  goldens and runtime runners remain under root `tests/`.
- Native generator/public API pin `1.3.0.dev2026103105`; generated binding runtime
  checks independently pin `1.2.0`. Linux x86-64-v3/glibc 2.35+ initially.
- Separate recursive CIR/MojoIR payload enums with named declaration references,
  standard smart pointers, borrowed passes, private builders and fresh outputs.
  No flat type store, memoization or custom ownership framework.
- Preserve algorithms, Unicode names, ABI decisions, diagnostics and generated
  binding/layout sources. Debug IR JSON is unversioned and follows the code.

## Stages and completion gates

| Stage | Deliverable | Gate |
| --- | --- | --- |
| 0 | Toolchain, repository, ownership tests and CI | Recursive payload lifecycle at O0/O3 |
| 1 | Recursive types, pure mapper and codecs | Complete type-family parity |
| 2 | Expressions, declarations, facts, normalization and backend | Semantic IR and byte-identical sources |
| 3 | libclang frontend and complete native pipeline | Supported corpus without Python generation |
| 4 | One PyPI/Conda product, Python presentation, public Mojo interfaces | Installed artifacts, public API, relocation and runtime checks |
| 5 | Mojo generation by default; isolate previous Python algorithms | Native acceptance independent of Python reference |

The implementation and package gates for stages 4–5 are in
[native_distribution_cutover.md](native_distribution_cutover.md). Publication is
separate: build candidates and CI configuration do not constitute a release.
The previous Python tree remains deliberately available under `legacy/python/`
for optional comparisons, rather than being included in the installed package.

## Distribution contract

The PATH command is `mojo-bindgen`. Its Python facade runs the same-named public
executable at the package's documented payload path. `--print-mojo-path` exposes
the public library location. Conda also installs that library on its compiler's
normal import path. There are no native-specific product names.

The wheel declares exact compiler/libclang dependencies; the pinned nightly uses
Modular's extra wheel index. Conda uses its corresponding native packages and
checksum-pinned `libclang_mojo` GitHub artifact. `.mojoc` compatibility requires the
exact producing compiler. System Clang handles preprocessing/probes; packaged
Clang resource headers keep frontend builtin discovery deterministic.

Tagged releases verify one version across all interfaces, render immutable Git
sources, build/test installed artifacts, publish checksummed GitHub channel assets
and then publish the wheel/sdist. No ordinary main push uploads packages.

Permanent acceptance uses Mojo TestSuite plus a standard-library process/build
coordinator with bounded parallelism and shared caches. The legacy environment
is a separate opt-in/live differential lane and a tagged-release comparison gate.
See [native testing](native_testing.md), [frontend evidence](native_frontend_plan.md)
and [the public guide](../mojo/README.md).

The following records describe the earlier stages at their original boundaries.

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


## Backend-slice validation (2026-11-01, Linux x86-64)

The native backend now generates bindings and layout-test source from constructed
CIR. Production modules mirror Python's analysis/CIR/facts/mapping/codegen/layout
boundaries. Full declaration/expression/root codecs remain unversioned debug data.
The production Python generator and root stable toolchain remain unchanged.

- Full suite: **456 passed**, including 20 backend differential/runtime tests and
  14 type differential/compiler-contract tests.
- Light gate: formatting, Ruff, Pyright and **396 tests passed; 60 deselected**.
- Native build/formatting passed. All 12 native ownership/codec/recovery tests
  passed at both O0 and O3.
- 49 shared headers match Python's intermediate IR and byte-identical binding and
  layout sources in both link modes at both optimization levels. Constructed IR
  additionally covers large exact integers, numeric edge cases, options and ABI
  differences, Unicode, structural cycles, sharing, and error recovery.
- Native-generated bindings passed stable-toolchain runtime checks for three
  representative fixtures in both modes. A local Conda package passed installed
  import and backend-generation checks outside the checkout; nothing was uploaded.

At that milestone, system `max_align_t` and split-padding layout reflection
retained the Python reference limitations. The coordinated
[representation safety changes](representation_safety.md) now resolve both and
remove their runtime exclusions. Native parsing and CLI header generation were
still stage 3 work at this original milestone.


## Real example JSON follow-up (2026-11-01)

Actual Python CLI CIR and MojoIR dumps for zlib, Cairo, libpng, and SQLite now
continue through a standalone native driver. All 16 example/mode/optimization
cases passed, including 32 JSON-stage handoffs, exact source parity, and stable
runtime smoke tests. The full suite now passes **472 tests**; the light gate
passes **396 tests with 76 deselected**. See [commands, scope and measured results](
native_json_handoff.md). Example headers and runtimes use an independent locked
environment; both compiler dependency locks remain unchanged.


## Frontend-slice validation (2026-11-01, Linux x86-64)

Stage 3 is implemented and validated. The native command parses C headers directly
using the checksum-pinned shimless GitHub libclang_mojo release. Python remains the
canonical generator and independent test reference; no command cutover or package
publication occurred.

- Full suite: **506 passed**. Light gate: format/Ruff/Pyright and **400 passed,
  106 deselected**.
- **18 native tests at O0/O3** pass, plus native build/precompilation/formatting.
- All 49 shared headers match raw CIR, finalized MojoIR, binding and layout source
  in both modes at O0/O3. Extra tests cover target and char policy, unsigned enums,
  Unicode, bitfields, diagnostics, failure recovery and calling-convention rejection.
- Direct native headers and retained Python JSON handoffs for all four examples
  pass **32 example/mode/optimization cases** and stable binding runtime checks.
- Final local Conda build and installed compiled API/CLI generation tests pass.

See [the frontend implementation and dependency provenance](native_frontend_plan.md)
for dependency provenance, upstream unsaved-file ownership and traversal fixes,
exact folding comparisons and test scope. Stages 4–5 remain future work.


## Shared acceptance follow-up (2026-11-01)

Surface/alignment, corpus, stress and all existing runtime tests now share their
test bodies across Python, native O0 and native O3. The 198-case shared matrix and
full **638-test suite** pass; the light gate remains at **400 passed**. Native
shared acceptance is required by `check-native`. See [the harness boundary,
selection and measured results](shared_header_acceptance.md). Production generator
algorithms and fixed expectations remain unchanged in this follow-up.

The next shared slice adds type lowering, macro closure/expansion/folding, comment
capture/emission and target ABI checks. All 102 shared behaviors now run across
three harnesses (306 executions; 204 native). Full integration passes **710 tests**;
the light gate remains **400 passed**, with no production or expectation changes.

The backend shared-test slice adds declaration/expression mapping, constructed-IR
emission, normalization/printing and layout checks, plus numeric and debug-codec
failure/recovery contracts. Shared coverage is now 186 behaviors across three
harnesses (558 executions, 372 native). The full suite passes **891 tests** and
the light gate **413 tests**. `native-shared` discovers all native-marked shared
cases automatically. Production algorithms and fixed goldens are unchanged.

## Native testing prerequisite for slice 4

Native TestSuite programs now own the former native pytest acceptance assertions.
A permanent Python standard-library coordinator handles discovery, bounded parallel
compilation/execution and shared content-keyed caches; it imports no Python bindgen
or pytest. Python comparisons remain a separate coexistence lane. The coverage
inventory, research, gate contract and integration measurements are recorded in
[native testing](native_testing.md). Slice 4 requires that independent gate.

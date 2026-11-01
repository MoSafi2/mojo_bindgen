# Shared Python/native header acceptance

This is the historical pytest-sharing ledger. The native executions described
below have moved to independent Mojo TestSuite programs; `--bindgen` selection
and native pytest adapters have been removed. Python behavior tests now exercise
Python only. Current commands, coverage and measured results are in
[native testing](native_testing.md).

The native frontend was committed separately as `74be8d5` before this migration.
This slice shares the existing surface/alignment, corpus, stress and runtime test
bodies across Python, native O0 and native O3. No golden/status/runtime expectation
is changed, and production generator algorithms remain unchanged.

## Test boundary

- `tests/header_harness.py` owns test-only Python and native adapters plus a small
  common header interface. Session-scoped compiled binaries are reused by source
  and optimization; parsed/mapped results are never cached.
- Python parsing/generation/codecs call existing Python APIs; CLI tests run the
  actual Python CLI. Native parsing, generation and codecs run the compiled
  backend test driver. Runtime generation uses the actual native CLI.
- Native debug JSON is decoded into current Python IR assertion views solely to
  reuse existing isinstance/field checks. This does not call Python algorithms
  for native results or introduce serialized schema versions. Future tests should
  prefer plain behavioral assertions to ease final Python IR retirement.
- `backend_driver.mojo` gains a header-parse request and forwards all existing
  emission options, including strict ABI used by alignment goldens. Unsupported
  origin values fail explicitly. Stage-specific decoders remain authoritative.
- Source parse errors have a shared test exception; compiler/driver failures remain
  separate errors rather than being mistaken for expected source failures.
- The stress roundtrip test invokes each implementation's own CIR codec, including
  the native codec, instead of roundtripping both implementations through Python.
- Runtime runners are copied beside the selected implementation's fresh bindings.
  Case artifacts no longer overwrite ignored output in shared fixture directories.
  Native subprocess runtime libraries do not leak into stable compilation/runtime.

## Selection and gates

`--bindgen all` (default) runs Python and both native optimizations. Optional native
SDK absence is an explicit skip in this mode. `--bindgen python` runs only Python
shared cases; `--bindgen native` requires the native SDK and runs O0/O3. This option
controls shared suites; existing differential tests keep their own matrix.

Native parameters have `native` and `expensive` marks. `check-light` preserves its
400 Python/light cases. `native-shared` runs native surface/corpus/stress/e2e and
the parser behavior slice, selecting only `native`-marked cases. It
is a dependency of `check-native`, which CI already invokes after installing the
native lock and examples. Existing native ownership/compiler and differential
coverage stays separate.

The initial slice has 40 surface/corpus/stress cases and 26 runtime cases per
harness, yielding 198 shared executions; the parser slice below adds 108. The runtime cases include both linking modes, real C
libraries, and unsafe-varargs negative compilation expectations.

## Validation (2026-11-01, Linux x86-64)

- Shared surface/corpus/stress/runtime matrix: **198 passed** in 224.94 seconds.
  Each of the 66 original cases runs with Python, native O0 and native O3.
- Full suite: **638 passed** in 367.87 seconds. Existing differential, example,
  unit, CLI and stable-SDK runtime/negative-compilation coverage remains active.
- Light gate: format, Ruff and Pyright pass; **400 passed, 238 deselected**.
  The original light-test count is unchanged.
- Native formatting passes. Native-only selection collects **132 cases**, which
  are also exercised successfully in the complete shared/full matrices.
- No golden, status, runtime expectation, shared header or C fixture changed.
- Production Python/native generator algorithms and dependency locks are unchanged.
  The native test driver alone gains the additional parse/options transport.

The stable FFI CI job explicitly selects Python; `check-native` now requires
`native-shared` in addition to its existing gates. This prevents optional SDK
availability skips from substituting for required native acceptance in CI.


## Parser behavior slice (2026-11-01)

The next slice shares 36 existing cases: 19 type-lowering cases, 13 macro
closure/helper cases, two doc-comment cases, and two target-ABI cases. The
Python-specific context-enum assertion and two printer-cleanup helper tests remain
Python-only. Assertions and generated expectations are unchanged.

The test adapter now forwards explicit compile arguments, include headers, and
opt-in Clang macro evaluation. Native requests also expose the production constant
folder, macro expander, and object-macro collector. The Python collector's private
parser session stays inside its adapter. Python's optional fallback scratch-directory
argument remains supported; native fallback uses an owned unsaved translation unit
and creates no scratch files.

This raises shared coverage to 102 cases per harness: 306 shared executions, of
which 204 are native O0/O3 cases. No production implementation changes are needed.

Focused parser validation passes: **39 Python cases** (including three local
helper assertions) and **72 native cases** at O0/O3. The expanded native selector
collects **204 cases** and excludes the three Python-only helpers. The light gate
passes formatting, Ruff, Pyright and **400 tests, 310 deselected**. Native
formatting also passes.

Final integration: **710 passed in 380.24 seconds**, including all 306 shared
executions and existing differential, runtime and negative-compilation coverage.

## Upstream frontend fixes (2026-11-01)

The refreshed pinned libclang package removes the cursor child-count cap and
retains unsaved buffers through parsing. Native code now calls `Index.parse`
directly. A new shared regression checks that all 4,100 function declarations
survive parsing in order. Coverage is now 103 shared behaviors (309 executions;
206 native), with 401 light tests. Prior measured counts above are historical.

Refresh acceptance: **713 passed** in the full suite; focused parser matrix
**114 passed**, native unit executions **36 passed**, light gate **401 passed**.

## Backend behavior slice (2026-11-01)

71 existing backend cases now share their original assertions across Python,
native O0 and native O3:

- `test_analysis_const_mapping.py`: two expression-mapping cases.
- `test_analysis_unit_mapping.py`: 20 declaration-mapping cases.
- `test_ir_codegen_edges.py`: 24 constructed-IR binding-emission cases.
- `test_layout_tests.py`: seven layout collection/sidecar cases.
- `test_mojo_ir_printer.py`: 18 normalization/printing cases, including two stable
  compiler checks. Its two private serialization-helper cases and one monkeypatch
  test remain Python-only.

Eight new expression cases cover signed zero, very small/large decimal values,
hexadecimal floats, large integers, shared recursive children, independent ABI
contexts, repeated mapping and recovery after rejected nullptr mapping. Four new
debug-codec cases reject unknown tags and wrong-stage roots, preserve supplied
payloads, and successfully decode valid inputs after failures.

Adapters expose direct expression/unit mapping, whole-pipeline analysis, target
normalization, printing, layout collection/rendering and stage-specific debug
decoding. The native driver invokes production Mojo passes. Python constructs
assertion-view dataclasses from debug output but performs no native analysis. The
printer test's original analysis setup also goes through the selected harness.
Error adapters translate decoder and expression-mapping rejection into the common
test exception; compiler/transport failures continue to fail tests. Decoder
recovery verifies the callable adapter remains usable; existing same-process
native differential tests retain their stronger internal-state recovery checks.

The `native-shared` task now selects `--bindgen native -m native` across normal
pytest discovery. This includes every shared fixture parameter automatically and
excludes Python-only tests and separate differential suites. The selector collects
**372 native cases**: 186 behaviors across O0/O3. All three harnesses yield **558
shared executions**. Fixed goldens, production algorithms and dependencies are
unchanged.

Focused migrated/native expression matrix: **158 passed**. Final integration below
also verifies the analysis-setup cleanup and four new codec cases.
Light gate: format, Ruff, Pyright and **413 passed, 478 deselected**. Native
formatting passes.

Final integration: **891 passed in 380.35 seconds**, including all **558 shared
executions** (372 native), existing differential checks, stable generated-binding
runtime/negative-compilation tests, and the final analysis/codec wiring.

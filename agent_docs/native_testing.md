# Native acceptance

## Boundary

The agreed permanent coordinator is Python standard-library-only. TestSuite and
Mojo assertions own native acceptance; pytest and the Python bindgen modules are
not runtime dependencies of this gate. `python -I -S scripts/run_native_tests.py`
runs it without site packages or the checkout root on Python's import path.
The compiler itself still brings its own Python tooling transitively.

Native generation/tests use Mojo `1.3.0.dev2026103105`. Generated bindings use the
separate `stable-tests` environment pinned to Mojo `1.2.0`. The native development
manifest declares the coordinator's Python dependency explicitly. The root Python package is now a CLI facade. The isolated previous generator
and live comparison harness remain under `legacy/python/`.

## Implementation

- `scripts/native_testing/` is the single build/process authority. Normal test
  files use standard `TestSuite.discover_tests[__functions_in_module()]()`;
  discovery/filtering is delegated to `--skip-all`/`--only`, not source parsing.
- The full gate builds seven fixed subsystem suites (backend, frontend, fixtures,
  vectors, runtime, compiler contracts and examples) plus the five typed unit
  programs. Subsystem suites register the original Mojo test functions through
  `TestSuite.test`; they do not duplicate assertions. This avoids compiling the
  common native support repeatedly for every small fixture file. The original
  files remain standalone TestSuite entry points for focused work. There is no
  selection-dependent generated source or single giant compilation unit.
- Workers default to four running suites, two compiler processes and one compiler
  thread each, bounded by CPU count. O0/O3 share a build authority and never share
  mutable scratch. Source/SDK/include/link inputs, flags and x86-64-v3 are keyed
  by content. Completed executables publish under a per-key lock; failed builds
  are not cached. Tests always run again. Compiler caches are SDK-specific.
- Separate process groups enforce deadlines. A compiler rejection, assertion,
  crash, missing tool, timeout or incomplete TestSuite report cannot become a
  successful empty run. Exit status and case/summary counts are both checked.
- Each fixture suite first prepares its native results and generated sources.
  The coordinator handles C/stable/native subprocess mechanics and writes their
  outcomes. The suite then checks outcomes and expected data in Mojo. Expected
  compiler rejections are executed every time. Runtime tolerances and the known
  large-alignment layout failure are preserved.
- CLI, parser, mapping, codecs, printing, layout and runtime expectations now
  execute in Mojo. Python tests run only Python; live differential comparisons
  remain a separate coexistence lane and reuse the same content-keyed native
  driver builds. The old native pytest adapters are removed.

## Coverage and reference data

`tests/mojo/fixtures/inventory.json` maps every one of the 186 formerly shared
behaviors to a native function. It also registers differential vector coverage,
CLI/target/Unicode/diagnostic checks, examples, layout runtime and stage compiler
contracts. Existing typed ownership/construction tests remain separate. Discovery
is checked against the inventory so deleting a wrapper cannot silently drop a case.
There are 226 fixture behaviors and 18 typed native tests per profile: 488 test
executions across O0 and O3.

The reference vectors were captured offline from the Python implementation while
its original assertions passed, using the *same pinned libclang runtime* as the
native frontend. They were not generated from native results. Whole semantic IR
and output checks supplement the former field/snippet assertions. Fixture paths
are expanded to their workspace locations before comparison. Declaration IDs,
names, geometry, array order and literal strings match exactly; only JSON object
key order is ignored.

Large vectors are deterministic gzip JSON, about 4 MiB together, rather than
70+ MiB of repetitive checked-out data. The coordinator only decompresses/copies
this data. Native code decodes it and asserts results. Inspect a case using
`gzip -dc tests/mojo/fixtures/acceptance/GROUP/CASE.json.gz`.

These are current-model, unversioned debug fixtures. Schema changes deliberately
update them with the codecs; no migration/legacy decoder exists. The inventory
keeps original test IDs and fixtures retain reference provenance/source-assertion
hashes, independently of the retained optional Python reference tree. Future changes should
prefer focused typed Mojo tests or reviewed fixture edits. Never regenerate
expected output from the native implementation merely to make a failure pass.

## Commands

Install the default/stable native environments and the separate example manifest
before full acceptance. The native Pixi `test` task already runs Python with
`-I -S`.

```
pixi install --manifest-path mojo/pixi.toml --locked
pixi install --manifest-path mojo/pixi.toml --locked -e stable-tests
pixi install --manifest-path examples/pixi.toml --locked
pixi run --locked native-test
pixi run --locked native-shared
python -I -S scripts/run_native_tests.py --suite runtime --optimization 3
python -I -S scripts/run_native_tests.py tests/mojo/unit/test_backend.mojo::test_context_is_bound_to_source_unit
python -I -S scripts/run_native_tests.py --list --suite unit
python -I -S scripts/test_native_runner.py
```

`--jobs`, `--compile-jobs`, `--compiler-threads` and timeouts are explicit controls.
`--no-cache` bypasses the executable store; `--clean-cache` clears only this
runner's build/compiler caches. Logs and dependency environments are retained.
JSON timing/cache reports and JUnit live under `mojo/build/native-testing/runs/`.
A warm run can still invoke compilers for expected-rejection cases; `built` counts
successful executable builds, not intentional compiler-rejection probes.

## CI and prior art

The native job installs only the native/stable SDKs and example libraries, then
runs the coordinator without Python site packages. The Python reference and differential lane is an explicit optional workflow and
a tagged-release gate. Required jobs check the facade/coordinator, native
acceptance and installed distributions. Trusted main pushes save native compiler
and executable caches; PRs restore them. Cache keys include SDK lock/OS/CPU identity and every executable is
validated by its own content key.
Reports are uploaded even on failure; failed jobs also retain JSON inputs, native
results and external-process outcomes for diagnosis. Installed-wheel and Conda checks run in the distribution job.

Reviewed precedents:

- [Mojo TestSuite](https://mojolang.org/docs/tools/testing/) and
  [stdlib build rules](https://github.com/modular/modular/blob/main/Mojo/stdlib/test/collections/BUILD.bazel):
  ordinary Mojo assertions/discovery, separate build and rejection infrastructure.
- [EmberJSON runner](https://github.com/bgreni/EmberJson/blob/e7feca8ebbdf2a338f586fed737bf8d01e6cad05/run_tests.py):
  bounded file-level subprocess parallelism, without carrying over loose output parsing.
- [Marrow runner](https://github.com/kszucs/marrow/blob/3462b909adf84e8d17f9cec17487f959d4b7c463/devkit/runner.py) and
  [compiler cache](https://github.com/kszucs/marrow/blob/3462b909adf84e8d17f9cec17487f959d4b7c463/.github/actions/mojo-cache/action.yml):
  shared compiler caches and manageable compilation units; no giant suite or pytest dependency.

## Integration evidence (2026-11-01, Linux x86-64)

- The Python/coexistence suite passes **519 tests**. The light gate passes
  formatting, Ruff, Pyright and **413 tests** (106 expensive cases deselected).
- Native formatting, library precompilation and executable build pass.
- The complete native gate passes **488/488 executions in 24/24 programs**, with
  no skips. The first grouped run takes **446.81 seconds**, with 125 successful
  executable builds and 151 cache hits (including stable runtime programs).
  The Conda build and installed native API/CLI generation checks also pass.
- A complete warm rerun again passes **488/488 executions**, taking **143.92
  seconds** with **zero executable builds and 276 cache hits**. Expected compiler
  rejection probes and C fixture builds still execute; successful test programs
  always execute again. Both complete runs use `python -I -S`.
- Final integration after removing the unnecessary declaration-ID relaxation
  again passes **488/488 executions with no skips**. This rerun takes **420.99
  seconds**, including 26 invalidated executable builds and 250 cache hits.
- **17 coordinator contract tests** pass without site packages. These cover report
  integrity, timeouts, SDK environment separation, concurrent publication,
  corruption, cold/warm reuse and invalidation by entry point, source, helper,
  dependency, SDK, target, linked library and optimization. Inputs changing during
  compilation cannot publish an artifact; clearing an active cache is rejected.

| Typed unit gate, both profiles | New executable builds | Executable hits | Wall time |
| --- | ---: | ---: | ---: |
| Serial, initially missing executables | 10 | 0 | 136.78 s |
| Serial, warm | 0 | 10 | 11.41 s |
| Four workers, warm | 0 | 10 | 9.58 s |

Compiler caches and executable caches are different: the timing measurements
above identify executable misses and retain the existing compiler cache. They are
local observations, not a hardware-independent benchmark. Distribution/cutover checks retain this complete native gate.

## Distribution cutover validation

The final 0.4 cutover gate again passes **488/488 executions in 24/24 programs**
at O0/O3, with no skips: 25 executable builds, 251 hits and 582.58 seconds on
this host. Report: `mojo/build/native-testing/runs/1793566669339504429-2419298`.
Installed-wheel checks additionally exercise PyPI/Conda libclang providers,
Clang selected through `cc`, the public Mojo API and stable generated FFI/layouts.
The isolated legacy suite passes 519 tests; it is not a native gate dependency.
See [distribution details](native_distribution_cutover.md) for artifacts and scope.

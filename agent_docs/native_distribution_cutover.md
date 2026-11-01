# Native distribution and Python CLI cutover

## Agreed scope

One product, `mojo-bindgen`, on PyPI and Conda. Python owns only Typer/Rich
presentation, completion and diagnostic rendering. It launches the installed
public Mojo executable by its package-relative path, never by PATH. All parsing,
analysis, generation, file/debug output and layout generation happen in Mojo.
There are no Python high-level generation bindings and no native-specific product
names. The public Mojo API and direct executable remain supported interfaces.

The previous Python implementation and its runnable environment/tests are isolated
under `legacy/python/`. It is excluded from installed artifacts and normal native
acceptance. Shared fixtures/goldens remain at root. The optional reference workflow
also gates tagged releases. This is a single 0.4.0 cutover, not a preview alias.

## Source and ownership boundaries

- `mojo/mojo_bindgen/`: native parser, analysis, mapping, codecs, normalization,
  binding printer and layout-test generator. Existing recursive contracts remain.
- `mojo_bindgen/`: Python facade and subprocess handling only. `__init__` exposes
  the release version, not the retired generator API.
- `tests/mojo/`: native TestSuite acceptance, with the standard-library coordinator
  under `scripts/native_testing/`. Root `tests/cli/` checks presentation/processes.
- `legacy/python/`: previous algorithms, pytest tests, typings and own Pixi lock.
- Root Pixi handles facade tooling and delegates native/reference commands to their
  isolated manifests. Generator nightly and generated-code stable SDK stay separate.

CLI argv is an argument list, including raw dash-prefixed Clang values and Unicode
paths. Binding stdout stays uncolored. Native diagnostic JSON is rendered by Rich
or forwarded as JSON; severity order, silent mode, output files and exit statuses
are preserved. Interrupts terminate/reap the native process group. Infrastructure
errors do not silently fall back to Python.

## Runtime dependencies

Generator and public `.mojoc` files pin **1.3.0.dev2026103105**, not the latest
moving nightly. Generated code is checked independently on **1.2.0**. Initial
artifacts support Linux x86-64-v3/glibc 2.35+ only.

PyPI wheels declare `mojo-compiler==1.3.0.dev2026103105` and
`libclang==18.1.1`. The former is on Modular's nightly wheel index and transitively
brings its matching standard library; no MAX/meta-package is needed. The latter
bundles standalone libclang, without separate LLVM/clang-cpp shared libraries.
The `clang` PyPI project contains bindings only. A system `clang` executable is
still required for preprocessing/probes. The install command therefore uses
`--extra-index-url https://whl.modular.com/nightly/simple/`.

Conda maps the same requirements to its exact compiler and Clang 18 packages,
plus the checksum-pinned upstream `libclang_mojo` artifact. Its installed Python
metadata does not request pip's libclang into that environment. The release channel
asset contains bindgen and the pinned upstream artifact; normal Conda channels
resolve the other dependencies.

Our payload contains only the executable, compiled public/imported Mojo modules,
Clang 18 builtin resource headers and release-specific notices. Runtime lookup is
relative to the installed package, with no checkout or build-prefix RPATH. The
executable configures libclang/resource paths; standalone Mojo API consumers can
configure those paths explicitly. `--print-mojo-path` exposes the supported library
location; Conda also installs the public module on the compiler's import path.

## Build and release mechanics

`hatch_build.py` invokes `scripts/prepare_distribution.py` for platform wheels;
editable installs do not build or pretend to include native code. Source artifacts
include production Mojo sources and the exact manifest/lock, never the reference
tree. Payload cache reuse verifies source/dependency identity and every file hash.
Compiler subprocesses use the selected SDK and system tool paths, dropping foreign
CC/CXX/LD, flags and library paths from another activated build environment. This
prevents cross-toolchain `GLIBC_PRIVATE` linker failures. Missing
compiler/patchelf/dependency notices fail the build. Notice fallback fetches
only the immutable package URL with its recorded SHA-256.

The Conda recipe builds/test-installs the same facade and payload. Tagged builds
render immutable Git sources; local builds use the checkout. Installed tests run
outside the source tree. `scripts/check_release.py` checks one release version
across the Python facade, Mojo VERSION, manifests and recipe, plus compiler pins.

CI requires facade/coordinator, native O0/O3 acceptance and installed distribution
jobs. Releases additionally run the Python reference suite, verify the exact tag
and source SHA, test artifacts, assemble a checksummed local Conda channel archive,
publish GitHub assets, then publish only the wheel/sdist to PyPI. Main pushes do
not publish. Published release assets cannot be silently replaced on retries.

No tag, package upload or Git push is part of this implementation task.

## Sources and future checks

- [PyPI libclang](https://pypi.org/project/libclang/18.1.1/): bundled standalone
  library and difference from the bindings-only `clang` project.
- [Modular nightly wheel index](https://whl.modular.com/nightly/simple/mojo-compiler/):
  exact compiler wheel availability; revalidate before a deliberate upgrade.
- [Mojo module compatibility](https://mojolang.org/docs/manual/packages/): exact
  compiler requirements for precompiled imports.
- [Native testing](native_testing.md): coverage, cache/parallelism, historical
  reference provenance and preserved layout limitations.

## Integration evidence (2026-11-01, Linux x86-64)

- The final native gate passes **488/488 executions in 24/24 programs** at
  O0/O3 with no skips (25 executable builds, 251 hits, 582.58 seconds). Report:
  `mojo/build/native-testing/runs/1793566669339504429-2419298/report.json`.
- The root format/Ruff/Pyright/light gate passes: **13 facade/distribution tests**
  and **17 standard-library coordinator tests**.
- The isolated Python reference passes **519 tests**. Its light gate passes
  formatting, Ruff, Pyright and **413 tests**, with 106 expensive cases deselected.
- Source-to-wheel builds pass. The platform wheel is about **4.63 MB**, compared
  with the first fully bundled candidate's **97.8 MB**. It contains no shared
  libraries. A fresh installation still downloads compiler/libclang dependencies;
  the reduction is to bindgen's own artifact, not the complete environment.
- Installed wheel checks compare **98 header/link-mode combinations** through
  direct execution and the facade, and across PyPI libclang 18.1.1 and Conda
  libclang 18.1.8. Binding and layout sources match byte-for-byte. Both debug IR
  dumps, diagnostic JSON, preprocessing, relocation and the installed public Mojo
  API pass. Generated calls and layouts compile/run independently on Mojo 1.2.0
  in both link modes.
- Resource-header selection excludes foreign Clang builtin headers, including
  when the system `cc` driver is Clang. An installed regression check covers the
  latter alongside the normal GCC-host comparisons. Mixing host Clang headers
  with packaged Clang 18 headers reproduced an unknown-`uint64_t` parse error.
- Unified Conda build and installed facade/direct/API checks pass. A fresh Pixi
  consumer resolves the assembled local channel and passes the same installed
  public interfaces, including default-path Mojo imports and Conda-only dependency
  metadata. Pixi consumers declare glibc 2.35 as their system requirement.
- Native formatting, precompilation/build and developer facade/direct smoke-source
  comparison pass. Workflow syntax passes actionlint. Binding/layout source goldens
  are unchanged. Existing layout limitations remain documented in `mojo/README.md`.

These are local candidates and local checks; no package, release tag or Git push
was published. Linux acceptance does not imply ARM/macOS support.

## Minimal OS verification (2026-11-01)

`scripts/test_minimal_install.py` now gates CI and tagged release builds. Its
official Python image is pinned to
`python@sha256:516b51cb9db2ef061e465c803e50f64361b82cefd91e525b889b967b83e83527`
on linux/amd64: Debian 12, Python 3.14.10, glibc 2.36. The base already contains
`libgcc-s1`/`libstdc++6` 12.2.0-14+deb12u1. These OS runtimes are not installed by
pip. No C compiler, linker, Clang executable or libc development headers exist in
the base image.

All three stages pass:

1. **Pip dependencies only:** facade/direct generation in both link modes,
   layout source, both debug codecs, help/version/completion (from Bash), and
   builtin `stdint.h`/`stddef.h` parsing. `stdio.h` reports a missing header;
   preprocessing reports missing Clang; compiling a Mojo consumer reports a
   missing toolchain. None is required for ordinary generation.
2. **Add only `libc6-dev`:** system `stdio.h` parsing/generation also passes,
   while no compiler/linker/Clang executable is present.
3. **Add `build-essential`:** the installed public Mojo API consumer compiles
   and runs. Clang remains absent, and preprocessing still fails as expected.

Each stage verifies the artifact's `Requires-Python: >=3.14` metadata and pip's
rejection of Python 3.13. No unrelated PyPI package named `python` is added.
Container probes use no host mounts, no network, an unprivileged UID, dropped
capabilities, a read-only root and disposable tmpfs workspaces. Only the wheel
and selected probe fixtures are copied into images. Runtime package versions,
the wheel checksum and pip's dependency URLs/checksums are in
`mojo/build/minimal-os/report.json`; logs are adjacent. Test image tags are removed.

This test exposed optional compiler probes printing `cc: not found` on otherwise
successful generation. The private process helper now supports quiet stderr for
those probes; required preprocessing commands retain their errors. The rebuilt
wheel passes the clean-container checks, and focused frontend tests pass at O0/O3.
Existing generated source contracts and toolchain pins are unchanged.

This verifies the named Debian/Python base, not every Linux distribution or the
glibc 2.35 lower bound. Third-party development headers remain caller-provided.

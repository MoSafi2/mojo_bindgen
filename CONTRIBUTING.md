# Contributing

Generation lives in `mojo/mojo_bindgen/`. The root `mojo_bindgen/` package is the
Python CLI facade only. The optional previous generator and its pytest suite live
in `legacy/python/`; they are not installed with the product.

## Development environment

Use locked Pixi environments on Linux x86-64. The generator/public Mojo library
pin Mojo `1.3.0.dev2026103105`; generated binding checks use an isolated Mojo
`1.2.0` environment. Do not mix their precompiled modules or runtime libraries.

```bash
mkdir -p mojo/build/test-tmp
pixi install --locked
pixi install --manifest-path mojo/pixi.toml --locked --all
pixi install --manifest-path examples/pixi.toml --locked
pixi run --locked native-build
pixi run --locked mojo-bindgen input.h -o bindings.mojo
pixi run --locked native-exec input.h -o direct.mojo
```

Root tasks:

- `test`: Python CLI/distribution unit tests using `unittest`.
- `test-light`: CLI tests and standard-library coordinator contract tests.
- `check-light`: Python formatting, Ruff, Pyright and light tests.
- `native-test`: Mojo TestSuite assertions at O0/O3, including fixture and stable
  generated-code runtime checks; no pytest or Python generator required.
- `native-shared`: surface/corpus/stress acceptance selection.
- `check-native`: native formatting, packaged build, coordinator and full tests.
- `build`: source distribution and Linux wheel in `dist/release/`.
- `example-zlib`, `example-cairo`, `example-libpng`, `example-sqlite`: facade
  generation followed by stable-toolchain checks using shared example libraries.

Install system C build tools and `clang` for preprocessing/probes. The native
manifest supplies Clang 18/libclang and packaging tools; the root environment
needs only CLI/development dependencies. `pip install -e ".[dev]"` is an alternative
for facade development, but does not build a native payload. Use
`MOJO_BINDGEN_EXECUTABLE` to select an already built executable.

## Tests and source organization

- `mojo/mojo_bindgen/parsing/`: libclang frontend, lowering and registry.
- `mojo/mojo_bindgen/analysis/`: CIR validation, facts and recursive mapping.
- `mojo/mojo_bindgen/codegen/`, `layout_tests/`: normalization and printers.
- `mojo/mojo_bindgen/ir.mojo`, `serde.mojo`: closed schemas and unversioned debug codecs.
- `tests/mojo/`: ordinary Mojo TestSuite programs, typed ownership tests, frozen
  reference vectors, runtime and compiler-contract acceptance.
- `tests/cli/`: facade and distribution unit tests.
- `tests/surface/`, `corpus/`, `stress/`, `e2e/`: shared headers, goldens and C/Mojo runners.

```bash
pixi run --locked check-light
pixi run --locked native-test
python -I -S scripts/run_native_tests.py --suite runtime --optimization 3
python -I -S scripts/run_native_tests.py --list --suite unit
pixi run --manifest-path mojo/pixi.toml --locked -e package package-build
pixi run --locked python scripts/test_installed_distribution.py dist/release/*.whl
pixi run --locked test-minimal-install dist/release/*.whl
```

Native workers share content-keyed successful executable caches and SDK-specific
compiler caches. Tests always execute again. See [native testing](agent_docs/native_testing.md)
for selection, timeouts, reports, coverage provenance and measurements.

The minimal-install gate requires Docker. It builds three disposable images from
a digest-pinned Python slim base: pip dependencies only, libc development headers,
then a C toolchain. Probes run without network access, as an unprivileged user,
with a read-only root filesystem and no host mounts. Logs and package/image
provenance are saved under `mojo/build/minimal-os/`; test image tags are removed.

Live comparisons remain available in an isolated, opt-in reference environment:

```bash
pixi install --manifest-path legacy/python/pixi.toml --locked
pixi run --locked legacy-test
pixi run --locked legacy-parity
pixi run --locked native-example-parity
```

New behavior belongs in Mojo. Keep fixtures shared, review output changes
explicitly, cover both link modes, and preserve known failures until deliberately
fixed. IR JSON is an unversioned debugging/testing representation: update codecs
and snapshots together, without migrations.

## Formatting and releases

Run `pixi run format` and the native manifest's `format` task before pushing.
`scripts/pre-commit.sh` formats, applies safe Ruff fixes, restages and runs
`check-light`. Native changes also require the appropriate native gates.

A release tag must agree with the Python facade, native VERSION, manifests and
Conda recipe. CI tests installed wheels outside the checkout, the public Mojo
API, direct execution, stable generated FFI/layouts and the installed Conda
package. Tagged releases additionally run the isolated Python reference suite.
Release Conda sources use an immutable Git SHA and upstream dependencies use
artifact checksums. Nothing is published by ordinary builds or main pushes.

Keep commit subjects concise and behavior-focused. PR descriptions should explain
the resulting behavior, relevant validation and deliberate fixture changes. See
[the distribution decision record](agent_docs/native_distribution_cutover.md).

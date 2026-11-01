# Contributing

Thanks for contributing to `mojo-bindgen`.

This repository is primarily a Python project that parses C with `libclang` and
emits Mojo FFI bindings. Most contribution work falls into one of three areas:

- parser changes under `mojo_bindgen/parsing/` and CIR-to-MojoIR mapping under `mojo_bindgen/analysis/`
- Mojo IR emission changes under `mojo_bindgen/codegen/`
- test and fixture updates under `tests/`

## Development environment

The repository currently targets:

- Python 3.14+
- Mojo 1.2+ (1.x), with the exact development version selected by `pixi.lock`
- a system `libclang` compatible with the Python `libclang` wheel
- Linux for the full Pixi + Mojo workflow

### Pixi (recommended)

Pixi is the primary workflow for this repo and is what CI uses on Linux.

The workspace is currently locked for `linux-64` only. On other platforms, use
a normal virtualenv and `pip install -e ".[dev]"` instead.

```bash
pixi install --locked
pixi shell
pixi run lint
pixi run format
pixi run typecheck
pixi run test
```

Useful Pixi tasks:

- `pixi run test`: full pytest suite
- `pixi run test-light`: pytest excluding `expensive` tests
- `pixi run check-light`: CI-aligned validation (`format-check`, lint, pyright, `test-light`)
- `pixi run --locked pytest -q tests/e2e --bindgen python`: the stable Python FFI runtime gate,
  including compiler warnings as errors and negative vararg compilation checks
- `pixi run build`: build sdist and wheel
- `pixi run example-sqlite` / `example-cairo` / `example-libpng` / `example-zlib`: generate and exercise example bindings

The default Pixi environment includes the `dev` feature set. If you only want a
smaller install environment with Mojo + editable `mojo-bindgen`, use:

```bash
pixi install -e install
pixi shell -e install
```

Set `LIBCLANG_PATH` if the shared library is not visible on the default loader
path.

## Repository workflow

Before pushing, run:

```bash
pixi run check-light
```

If you want formatting applied automatically first, run:

```bash
pixi run format
```

The repository includes a helper script at
[scripts/pre-commit.sh](scripts/pre-commit.sh) that:

- runs `pixi run format`
- applies safe Ruff fixes with `ruff check --fix`
- re-stages changes
- runs the same `check-light` validation as CI

If you want a local Git hook, symlink or copy that script into
`.git/hooks/pre-commit` yourself.

## Testing guidance

- parser / IR behavior: add or update unit tests under `tests/unit/`
- emitted Mojo surface changes: update surface expectations under `tests/surface/`
- ABI and runtime behavior: add or update cases under `tests/e2e/`

Targeted examples:

```bash
pixi run pytest -q tests/unit/test_mojo_ir_printer.py
pixi run pytest -q tests/surface
pixi run pytest -q tests/e2e -k fnptr_return
```

End-to-end tests require more setup than unit and surface tests because they
compile C and Mojo artifacts. See [tests/e2e/README.md](tests/e2e/README.md)
for the runtime matrix and fixture expectations.

When changing generated output, update tests deliberately rather than
re-baselining blindly. In particular:

- keep surface goldens honest about the exact emitted Mojo API
- keep e2e expectations aligned with both `external_call` and `owned_dl_handle`
- prefer conservative behavior over output that looks nicer but misrepresents C

## Native Mojo development

The native rewrite has its own pinned nightly manifest and lock under `mojo/`.
Use `pixi run --locked check-native` for native format/build checks, O0/O3
ownership tests, Python/native parity, and shared native acceptance suites. `pixi run --locked check-light` keeps
its existing stable-toolchain Python scope; the full pytest suite includes the
expensive native parity cases and therefore also requires Pixi and the native lock.
See [the native README](mojo/README.md) for setup, packaging and compiler constraints.


### Shared header and runtime acceptance

Surface/alignment goldens, corpus expectations, stress IR/codec checks, both
runtime suites, and parser behavior tests use the same test bodies and expectations
for three harnesses:
`python`, `native-O0`, and `native-O3`. Selection defaults to all available
implementations:

```bash
pixi run --locked pytest -q tests/surface tests/corpus tests/stress tests/e2e
pixi run --locked pytest -q --bindgen python tests/surface tests/corpus tests/stress tests/e2e
pixi run --locked native-shared
```

`--bindgen native` selects both native optimization levels and requires the locked
native environment. With the default `all`, unavailable native environments are
skipped with an installation command. Native cases carry `native` and `expensive`
markers, so `check-light` continues to run the Python cases. `check-native`
requires the native shared matrix in addition to differential tests.

The `bindgen` fixture in `tests/header_harness.py` provides header parsing,
CIR generation/roundtrips, constant folding, macro expansion/environments, and CLI
execution. The parser slice includes `test_type_lowering.py`, `test_macro_closure.py`,
`test_doc_comments.py`, and `test_target_abi.py` under `tests/unit/`. Python-only
enum and printer-helper tests remain outside the native matrix. Native algorithms execute in
compiled Mojo drivers or the native CLI. Python IR objects are test-only decoded
assertion views; they do not perform native parsing, mapping, or emission. Keep
new assertions independent of Python internals where possible, so these views
can be replaced when Python's IR is retired.

Shared fixed goldens and runtime expectations remain independent of differential
parity. Do not regenerate expected output from whichever implementation is being
tested. Preserve existing expected-failure statuses. Generated bindings and
copied runtime runners stay in each case's temporary directory, preventing stale
fixture-directory output from shadowing fresh bindings. Generated bindings always
compile/run on the separate stable SDK; nightly runtime variables are confined
to native generator subprocesses.

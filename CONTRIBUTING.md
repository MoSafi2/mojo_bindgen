# Contributing

Thanks for contributing to `mojo-bindgen`.

This repository is primarily a Python project that parses C with `libclang` and
emits Mojo FFI bindings. Most contribution work falls into one of three areas:

- parser / lowering changes under `mojo_bindgen/parsing/` and `mojo_bindgen/analysis/`
- Mojo IR emission changes under `mojo_bindgen/codegen/`
- test and fixture updates under `tests/`

## Development environment

The repository currently targets:

- Python 3.14+
- a system `libclang` compatible with the Python `libclang` wheel
- Linux for the full Pixi + Mojo workflow

### Pixi (recommended)

Pixi is the primary workflow for this repo and is what CI uses on Linux.

The workspace is currently locked for `linux-64` only. On other platforms, use
a normal virtualenv and `pip install -e ".[dev]"` instead.

```bash
pixi install
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

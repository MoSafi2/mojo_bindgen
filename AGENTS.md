# Repository Guidelines

## Project Structure & Module Organization

Production generation lives in `mojo/mojo_bindgen/`. The root `mojo_bindgen/`
contains only the Python CLI facade.

- `mojo/mojo_bindgen/parsing/`: libclang-driven parsing and C-to-IR lowering
- `mojo/mojo_bindgen/analysis/`: IR validation, reachability, and Mojo-facing analysis
- `mojo/mojo_bindgen/codegen/`: Mojo emission and generator orchestration
- `mojo/mojo_bindgen/ir.mojo`: separate recursive CIR and MojoIR schemas

Tests live under `tests/`:

- `tests/mojo/` for native TestSuite checks and `tests/cli/` for facade checks
- `tests/surface/` for parser/emitter goldens
- `tests/corpus/`, `tests/stress/`, and `tests/e2e/` for broader coverage

Supporting material lives in `examples/`, `docs/`, `scripts/`, `typings/`, and
`CONTRIBUTING.md`. The optional Python reference, tests and typings live in
`legacy/python/`.

## Build, Test, and Development Commands

Use Pixi on Linux; it is the primary workflow for this repo.

```bash
pixi install
pixi run test
pixi run test-light
pixi run lint
pixi run format
pixi run typecheck
pixi run check-light
pixi run build
```

- `pixi run test`: Python CLI/distribution unittest suite
- `pixi run test-light`: facade and standard-library coordinator tests
- `pixi run native-test`: complete native acceptance at O0/O3, including stable runtime
- `pixi run legacy-test`: opt-in isolated Python reference suite
- `pixi run check-light`: CI-aligned validation (`format-check`, lint, pyright, light tests)
- `pixi run build`: build sdist and wheel
- `pixi run precommit`: format, apply safe Ruff fixes, restage, and run `check-light`
- `pixi run example-zlib` / `example-cairo` / `example-libpng` / `example-sqlite`:
  generate and exercise example bindings

The default Pixi environment includes development tooling. Use
`pixi install -e install` for the smaller runtime-only environment.

Without Pixi, use `pip install -e ".[dev]"` for facade development and run
`unittest`, `ruff`, and `pyright` directly. Native generation still needs a built payload.

## Coding Style & Naming Conventions

Target Python 3.14+ with typed dataclasses and explicit, small helpers. Use 4-space indentation and keep lines within Ruff’s 100-character limit. Run `pixi run format` before pushing.

Naming patterns:

- modules/functions: `snake_case`
- classes/dataclasses: `PascalCase`
- constants and literal aliases: `UPPER_CASE`

Preserve the repo’s existing style: structured IR models, concise docstrings, and minimal comments.

## Testing Guidelines

Use Mojo TestSuite for generation/IR behavior and Python unittest for the facade.
The optional reference pytest configuration lives in `legacy/python/pytest.ini`.
When changing emission, update shared surface goldens deliberately. For example:

```bash
python -I -S scripts/run_native_tests.py --suite unit
```

## Commit & Pull Request Guidelines

Recent history favors short, imperative subjects such as `formatting`, `Fixes for Atomic Lowering in structs`, and `further seperation of codegen passes`. Keep commit messages concise and behavior-focused.

PRs should include:

- a clear summary of the change
- linked issues when relevant
- updated tests or goldens for behavior changes
- README or CHANGELOG updates for user-visible changes

Keep PRs focused; avoid mixing refactors, formatting, and feature work unless they are tightly coupled.

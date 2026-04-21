# Repository Guidelines

## Project Structure & Module Organization
Core source lives in `mojo_bindgen/`.
- `mojo_bindgen/parsing/`: libclang-driven parsing and C-to-IR lowering
- `mojo_bindgen/analysis/`: IR validation, reachability, and Mojo-facing analysis
- `mojo_bindgen/codegen/`: Mojo emission and generator orchestration
- `mojo_bindgen/ir.py` and `mojo_bindgen/mojo_ir.py`: C-facing IR and Mojo-facing IR schemas

Tests live under `tests/`:
- `tests/unit/` for fast isolated checks
- `tests/surface/` for parser/emitter goldens
- `tests/corpus/`, `tests/stress/`, and `tests/e2e/` for broader coverage

Supporting material lives in `examples/`, `docs/`, `scripts/`, and `plans/`.

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

- `pixi run test`: full pytest suite
- `pixi run test-light`: skips `expensive` tests for faster feedback
- `pixi run check-light`: CI-aligned validation (`format-check`, lint, pyright, light tests)
- `pixi run build`: build sdist and wheel

Without Pixi, use `pip install -e ".[dev]"` and run `pytest`, `ruff`, and `pyright` directly.

## Coding Style & Naming Conventions
Target Python 3.14+ with typed dataclasses and explicit, small helpers. Use 4-space indentation and keep lines within Ruff’s 100-character limit. Run `pixi run format` before pushing.

Naming patterns:
- modules/functions: `snake_case`
- classes/dataclasses: `PascalCase`
- constants and literal aliases: `UPPER_CASE`

Preserve the repo’s existing style: structured IR models, concise docstrings, and minimal comments.

## Testing Guidelines
Pytest is configured in `pytest.ini`. Name tests `test_*.py` and prefer narrow unit tests for new IR/passes. When changing emission behavior, add or update surface goldens under `tests/surface/`. Run targeted tests first, for example:

```bash
pixi run pytest -q tests/unit/test_ir_json_roundtrip.py
```

## Commit & Pull Request Guidelines
Recent history favors short, imperative subjects such as `formatting`, `Fixes for Atomic Lowering in structs`, and `further seperation of codegen passes`. Keep commit messages concise and behavior-focused.

PRs should include:
- a clear summary of the change
- linked issues when relevant
- updated tests or goldens for behavior changes
- README or CHANGELOG updates for user-visible changes

Keep PRs focused; avoid mixing refactors, formatting, and feature work unless they are tightly coupled.

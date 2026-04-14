# Testing Guide

`mojo_bindgen` uses layered tests so parser truth, codegen policy, and runtime
ABI behavior fail in different places.

## Layers

- `tests/unit/`
  Focused unit and integration tests for IR lowering, parser helpers, analysis,
  renderer behavior, and broad regression fixtures such as
  `tests/stress/normal/stress_normal_input.h`.
- `tests/surface/`
  Parser-driven Mojo surface goldens for representative headers. These tests are
  about emitted source shape, not runtime execution.
- `tests/corpus/`
  Header-zoo parser and IR checks. These cases may be parse-only or IR-only and
  do not need Mojo generation or runtime success.
- `tests/e2e/`
  End-to-end runtime fixtures that compile C code, generate Mojo bindings, build
  Mojo runners, and compare runtime outputs.

## Markers

Tests are marked automatically by directory:

- `unit`
  Applied to files under `tests/unit/`.
- `surface`
  Applied to files under `tests/surface/`.
- `corpus`
  Applied to files under `tests/corpus/`.
- `e2e`
  Applied to files under `tests/e2e/`.
- `integration`
  Applied to `surface`, `corpus`, and `e2e` tests.
- `slow`
  Applied to `e2e` tests.
- `expensive`
  Applied to `e2e` tests.

Useful commands:

- `pixi run pytest -q -m unit`
  Run only fast unit tests.
- `pixi run pytest -q -m "not expensive"`
  Skip the expensive runtime/toolchain tests.
- `pixi run pytest -q -m "surface or corpus"`
  Run parser/IR and emit-oriented integration checks without e2e runtime tests.
- `pixi run pytest -q -m e2e`
  Run only the expensive runtime suite.

## Choosing The Right Test

- Add a unit test under `tests/unit/` when the behavior can be expressed with
  hand-built IR.
- Add a surface fixture when the parser and renderer should agree on exact Mojo
  output for a representative header.
- Add a corpus case when a header shape should parse and round-trip in IR even
  if codegen/runtime support is incomplete.
- Prefer corpus cases for common, representative C constructs that should work
  normally, including anonymous-member patterns that are part of the supported
  surface.
- Use stress fixtures for pathological or extension-heavy anonymous-member
  shapes, especially deeply nested or mixed-layout forms that are easy to
  regress and may still be partially supported.
- Add an e2e fixture only when compiled/runtime ABI behavior matters.

## Corpus Cases

Each case under `tests/corpus/headers/<case>/` contains:

- `input.h`
- `status.json`
- `expect.ir.json`

`status.json` uses:

- `parse`: `pass | known_fail | unsupported`
- `ir`: `pass | known_fail | unsupported`
- `emit`: `pass | known_fail | not_required`

`expect.ir.json` is intentionally partial. It should assert the important IR
facts for the case instead of snapshotting the entire serialized `Unit`.

Corpus authoring rules:

- Keep each case focused on one primary declaration shape or policy edge.
- Prefer tiny headers: usually 5-20 lines and at most 3 top-level declarations,
  excluding helper typedefs/macros needed to express the shape.
- Use `known_fail` / `unsupported` when a parser or emitter gap is intentional
  and should stay visible in CI.
- Do not use corpus cases for exact emitted Mojo shape; use surface fixtures for
  that.

## Surface Cases

Each case under `tests/surface/fixtures/<case>/` contains:

- `input.h`
- `expect.external.mojo`
- `expect.no_align.mojo`

These are parser-driven goldens for representative emitted bindings.

Surface authoring rules:

- Keep one primary codegen behavior per fixture.
- Prefer tiny headers over broad composite examples.
- Comment-stub output is a valid golden when the current intended behavior is to
  surface an unsupported shape honestly rather than emit a callable wrapper.

## Prior Art

- Rust compiletest/UI favors many small categorized fixtures with local
  expectations instead of one giant integration test.
- `rust-bindgen` separates generated binding checks from runtime/layout-focused
  validation.
- `cffi` distinguishes declaration preservation from compiler/runtime
  validation, which maps well to this repo's parser/IR corpus plus e2e runtime
  split.

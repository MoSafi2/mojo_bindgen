# Testing Guide

`mojo_bindgen` uses layered tests so parser truth, codegen policy, and runtime
ABI behavior fail in different places.

## Layers

- `tests/unit/`
  Focused unit and integration tests for IR lowering, parser helpers, analysis,
  renderer behavior, and broad regression fixtures such as `everything.h`.
- `tests/surface/`
  Parser-driven Mojo surface goldens for representative headers. These tests are
  about emitted source shape, not runtime execution.
- `tests/corpus/`
  Header-zoo parser and IR checks. These cases may be parse-only or IR-only and
  do not need Mojo generation or runtime success.
- `tests/e2e/`
  End-to-end runtime fixtures that compile C code, generate Mojo bindings, build
  Mojo runners, and compare runtime outputs.

## Choosing The Right Test

- Add a unit test under `tests/unit/` when the behavior can be expressed with
  hand-built IR.
- Add a surface fixture when the parser and renderer should agree on exact Mojo
  output for a representative header.
- Add a corpus case when a header shape should parse and round-trip in IR even
  if codegen/runtime support is incomplete.
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

## Surface Cases

Each case under `tests/surface/fixtures/<case>/` contains:

- `input.h`
- `expect.external.mojo`
- `expect.no_align.mojo`

These are parser-driven goldens for representative emitted bindings.

## Prior Art

- Rust compiletest/UI favors many small categorized fixtures with local
  expectations instead of one giant integration test.
- `rust-bindgen` separates generated binding checks from runtime/layout-focused
  validation.
- `cffi` distinguishes declaration preservation from compiler/runtime
  validation, which maps well to this repo's parser/IR corpus plus e2e runtime
  split.

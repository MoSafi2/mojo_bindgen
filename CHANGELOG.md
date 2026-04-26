# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- added CIRCanoncanlizer pass, for now only deduplicates IR nodes. [f9b4156](https://github.com/MoSafi2/mojo_bindgen/commit/f9b4156d5be1d8123c6256a68966d23c8778246c)

## [0.1.1a] - 2026-04-24

### Added

- First public alpha release of `mojo-bindgen`.
- CLI packaging for `mojo-bindgen`, including PyPI metadata, MIT license, and
  `py.typed`.
- `libclang`-based C parsing and structured lowering through CIR and Mojo IR.
- Mojo code generation for both `external_call` and `owned_dl_handle` linking modes.
- Support for core C surfaces including scalars, typedef chains, pointers,
  arrays, structs, unions, enums, bitfields, callbacks, globals, constants,
  and a supported subset of object-like macros.
- Numeric lowering for Mojo-native constructs including `SIMD[...]`,
  `ComplexSIMD[...]`, and representable `Atomic[...]`.
- JSON IR output support for debugging and downstream tooling.
- Worked examples for SQLite, Cairo, libpng, and zlib.
- Development tooling and automation: Ruff, Pyright, Pixi tasks, CI validation,
  and release publishing workflow.

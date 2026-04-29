# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- added CIRCanoncanlizer pass, for now only deduplicates IR nodes. [f9b4156](https://github.com/MoSafi2/mojo_bindgen/commit/f9b4156d5be1d8123c6256a68966d23c8778246c)
- Generate optional Mojo record-layout test sidecars from normalized CIR facts,
  including `--layout-tests`, `--no-layout-tests`, `--layout-test-output`, and
  the `generate_mojo_artifacts` Python API.

### Changed

- Split bindgen into explicit parsing, analysis, codegen, and top-level
  orchestration layers. The new public surface is
  `BindgenOptions` / `BindgenOrchestrator` / `BindgenResult` / `bindgen`, and
  the old `MojoGenerator` / `generate_mojo` / `generate_mojo_artifacts` /
  `analyze_to_mojo_module` APIs are removed.
- Unify MojoIR callable signatures under `FunctionType` so function-pointer
  lowering, callback typedefs, and callback aliases all share the same schema.
  This removes the separate `CallbackType` / `CallbackParam` MojoIR shape.
- Make synthesized bitfield accessors branch at comptime on
  `std.sys.info.is_little_endian()` / `is_big_endian()` while keeping target
  byte order in `TargetABI` for ABI metadata instead of printer-side selection.
- Lower exact-width stdint typedef aliases such as `int32_t`, `uint32_t`,
  `int64_t`, and `uint64_t` to Mojo fixed-width integer types while preserving
  ordinary C ABI scalar aliases such as `c_int` and `c_long`.
- Lower `size_t` and `ssize_t` typedef aliases to Mojo native `UInt` and `Int`
  respectively instead of emitting FFI scalar builtins.
- Remove the stale, unused `ffi_scalar_style` emit option and public
  `FFIScalarStyle` export.
- Lower named CIR enums into `StructDecl(kind=ENUM)` in MojoIR instead of a
  separate `EnumDecl` shape.
- Add struct-local `comptime` members to MojoIR so enum constants and similar
  in-struct aliases can be represented and rendered directly from `StructDecl`.
- Replace MojoIR module capability toggles with a concrete dependency container
  that records imports and support helpers explicitly for normalization and
  printing.

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

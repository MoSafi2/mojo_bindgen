# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Changed

- Avoid invalid Mojo in `owned_dl_handle` wrappers when a C parameter name
  collides with the generated function-pointer local, and use a clearer
  `_bindgen_c_fn` internal name.

## [0.3.1] 2026-06-18

### Changed

- Update generated Mojo bindings, layout-test sidecars, and example smoke tests
  for Mojo 1.0.0b2 syntax changes, including `def`, explicit `abi("C")`,
  `reflect[T]`, and the new `UntrackedOrigin` / `UnsafeAnyOrigin` spelling
  family.

## [0.3] 2026-06-01

### Added

- Capture C documentation comments from libclang and emit them into generated
  Mojo bindings, with `--doc-comments` / `--no-doc-comments` control.
- Add repeatable `--include-header` support for parsing multiple public entry
  headers through a virtual umbrella translation unit.
- Add an opt-in Clang macro fallback for unsupported integer macro expressions,
  broader macro constant folding for logical/comparison/ternary forms, string
  literal concatenation and escape decoding, and regression coverage for macro
  closure and canonicalization behavior.
- Handle repeated field types in anonymous unions by still lowering them to
  `UnsafeUnion`,  (@WolfDan; PR #9).
- Lower flexible array member declarations as `InlineArray[T, 0]` instead of
  deriving their size from the containing struct,  (@WolfDan; PR #9).
- Detect trailing C99 flexible array members (`[]`) and GNU zero-length tail
  arrays (`[0]`) explicitly during record lowering, carry their metadata
  through CIR and MojoIR, and emit generated tail-access helpers plus runtime
  coverage for both forms.

### Changed

- Generate layout-test sidecars with `TestSuite.discover_tests[__functions_in_module()]().run()`
  in `main` and import `TestSuite` from `std.testing` so the generated module
  runs its own discovered tests directly.
- Resolve layout-test reflection offsets from emitted Mojo member order instead
  of CIR field indices, so generated checks stay aligned when padding members
  are inserted before named fields or bitfield groups.
- Lower named C enums to scalar Mojo type aliases plus typed top-level
  enumerator constants, preferring typedef names as the primary emitted alias,
  emitting collision-free tag aliases when possible, and keeping anonymous
  enums on the existing constants-only path.
- Emit top-level declarations and source-backed macros from the parsed
  translation unit instead of filtering to configured header paths, including
  transitive include declarations and macros.
- Keep source-backed macro folding aligned with emission: object-like macros
  from the emitted translation-unit macro set are available for expansion, while
  compiler/predefined no-file macros are neither emitted nor used for folding.
- Treat integer macro literals as signed by default when no suffix, parsed cast,
  or Clang-provided type information says otherwise, while preserving explicit
  unsigned suffixes and Clang-resolved integer types.
- Prune empty source macros from the parsed IR and suppress any empty macro
  declarations that reach Mojo lowering, so they no longer emit placeholder
  comments or aliases.
- Rename the orphan-record reachability repair to signature-only record stub
  materialization, and keep it only for references like
  `int f(struct opaque *p);` that have no standalone top-level record cursor.
- Retain documentation comments from system headers during parsing when
  doc-comment emission is enabled, while preserving the default probed include
  search path so header-heavy examples like SQLite continue to parse.
- Treat structs with flexible tail arrays as memory-only header-prefix types,
  reject by-value embedding of such structs from typed layout lowering, and
  keep one-element tail arrays (`[1]`) as ordinary fixed arrays.

### Removed

- Remove parser-side embedded-record materialization and primary-header cursor
  compatibility aliases now that the parser lowers translation-unit cursors
  directly.

## [0.2.1] - 2026-05-01

### Changed

- Bump the package version to `0.2.1` and update the release tag naming to use
  the `compiler` suffix.

## [0.2] - 2026-05-01


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
- Unify MojoIR callable signatures under `FunctionPtr` so function-pointer
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
- Render synthesized struct padding as aligned Mojo integer fields so padded
  records can remain register-passable when their real fields are passable.
- Remove the stale, unused `ffi_scalar_style` emit option and public
  `FFIScalarStyle` export.
- Lower named CIR enums into `StructDecl(kind=ENUM)` in MojoIR instead of a
  separate `EnumDecl` shape.
- Add struct-local `comptime` members to MojoIR so enum constants and similar
  in-struct aliases can be represented and rendered directly from `StructDecl`.
- Replace MojoIR module capability toggles with a concrete dependency container
  that records imports and support helpers explicitly for normalization and
  printing.
- Render C data pointers as `Optional[UnsafePointer[...]]` or optional opaque
  pointer aliases so generated Mojo signatures represent nullable C pointers
  explicitly.
- Update generated layout-test sidecars to use the newer Mojo reflection API
  (`reflect[T]()` with `field_offset[...]()`) instead of the legacy
  `offset_of[...]()` form.

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

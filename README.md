[![CI](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml/badge.svg)](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml)

# mojo-bindgen

> [!WARNING]
> Alpha stage: this project is under heavy development and may change quickly.

**C headers -> Mojo FFI.** `mojo-bindgen` parses real C with
[libclang](https://pypi.org/project/libclang/), and emits Mojo bindings for `external_call` or
`owned_dl_handle` workflows. this mirrors the spirit of `rust-bindgen` which follows the same approch for `Rust`

The goal is simple: make binding generation easy and faithful as possible to the
actual C surface, and fail conservatively when a declaration cannot be modeled
correctly.

## Requirements

- Python 3.14+
- a system `libclang` compatible with the `libclang` Python wheel
- a Mojo (nightly) toolchain if you want to build or run the generated bindings

## Installation

### System dependencies

Install Clang and the shared `libclang` library first:

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y clang libclang1

# Fedora
sudo dnf install -y clang llvm-libs

# macOS (Homebrew)
brew install llvm
```

If the shared library is not on the default loader path, set `LIBCLANG_PATH`
to the directory containing `libclang.so` or `libclang.dylib`.

### Install from PyPI

```bash
pip install mojo-bindgen
```

PyPI package: [mojo-bindgen](https://pypi.org/project/mojo-bindgen/)

### Install from source

```bash
git clone https://github.com/MoSafi2/mojo_bindgen
cd mojo_bindgen
pip install -e .
```

For development setup, checks, and Pixi workflows, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Quick start

Generate bindings from a primary header:

```bash
mojo-bindgen path/to/header.h -o bindings.mojo --linking external_call|owned_dl_handle
```

Pass include paths and other Clang flags with repeated `--compile-arg`:

```bash
mojo-bindgen include/mylib.h \
  --compile-arg=-I./include \
  --compile-arg=-DMYLIB_FEATURE=1 \
  -o mylib_bindings.mojo
```

By default the parser uses `-std=gnu11` when no C standard is provided. Pin a
standard explicitly if your header requires one:

```bash
mojo-bindgen include/mylib.h --compile-arg=-std=c99 -o mylib_bindings.mojo
```

## Linking modes

`mojo-bindgen` supports two output styles:

- `external_call`
  Direct FFI wrappers. Use this when the target library is linked at Mojo build
  time.
- `owned_dl_handle`
  Dynamic runtime symbol lookup via `OwnedDLHandle` for loading a
  shared library (`.so`, `.dylib`).

Examples:

```bash
# default
mojo-bindgen include/mylib.h --linking external_call -o mylib_bindings.mojo

# runtime-loaded shared library
mojo-bindgen include/mylib.h \
  --linking owned_dl_handle \
  --library-path-hint /usr/lib/libmylib.so \
  -o mylib_bindings_dl.mojo
```

## What works today?

`mojo-bindgen` is still alpha and evolves quickly, but it already supports a
useful slice of real C headers and is practical today as a starting point for
generating bindings.

Current support includes:

- **Parsing and lowering:** real C parsing through `libclang`, repeatable `--compile-arg`
  support, and a structured IR pipeline rather than text-only generation.
- **Primitive types:** scalar types, typedef chains, pointers with const-aware
  mutability, fixed arrays, incomplete-array decay cases, complex values,
  vector extension types, and representable atomics.
- **Mojo-native numeric lowering:** vector types lower to `SIMD[...]`, complex
  values lower to `ComplexSIMD[...]`, and representable atomics lower to
  `Atomic[...]`.
- **Records:** structs, anonymous members, mixed layouts that combine plain
  fields and bitfields, synthesized padding, and custom alignment emission
  where Mojo can represent the layout faithfully.
- **Bitfields:** bitfields are emitted through explicit storage fields plus
  synthesized getter and setter methods.
- **Unions:** eligible unions lower to `UnsafeUnion[...]`; unions that cannot
  be represented safely fall back to opaque `InlineArray[...]` storage with
  diagnostics to preserve layout.
- **Opaque and difficult layouts:** incomplete records, packed layouts, and
  alignment-sensitive record shapes are preserved conservatively as opaque byte
  storage when a faithful typed layout is not possible.
- **Callbacks and function pointers:** callback typedefs, function-pointer
  fields, and function-pointer parameters and returns are preserved in Mojo via
  emitted `comptime` callback declarations and synthesized aliases when needed.
- **Functions:** thin wrappers are generated for non-variadic functions under
  both `external_call` and `owned_dl_handle` link modes.
- **Globals and constants:** because Mojo does not currently expose native C
  globals directly, supported globals lower through generated `GlobalVar` /
  `GlobalConst` helper structs with synthesized `load()` / `store()` methods;
  constants and supported object-like macros lower to `comptime` declarations.
- **Macros:** integer, float, string, and char literal macros, foldable macro
  chains, supported casts, and `sizeof(type)` expressions are emitted as Mojo
  code.
- **JSON IR output:** the CLI can emit serialized parser IR for debugging,
  testing, or downstream tooling.

## Current limitations

Known gaps you may still hit in generated code. For ABI-sensitive surfaces,
verify emitted layouts and symbols against your target toolchain.

- **Macros:** function-like macros, predefined macros, and more complex
  preprocessor behavior are preserved but usually emitted as comments for
  end-user review.
- **Variadics:** variadic C functions are not wrapped as callable thin-FFI
  bindings yet and are emitted as comment stubs.
- **Non-prototype / K&R-style functions:** older C declaration styles are only
  partially modeled and should be treated with caution.
- **Records with hostile layouts:** some packed, ABI-sensitive, or otherwise
  difficult record layouts cannot be emitted as fully typed Mojo structs and
  fall back to opaque storage; layout-sensitive declarations may still require
  manual verification.
- **Anonymous members:** anonymous struct and union members are preserved
  structurally, but they are not automatically promoted into a flattened parent
  record surface.
- **Atomics:** atomic support is conservative. Representable atomic fields and
  pointer-based usage work, but atomic globals are still emitted as stubs and
  some surfaces require manual handling.
- **Linkage and compiler edge cases:** `inline`, compiler-specific linkage
  hints, and other extension-heavy cases can still require manual review and
  may lead to symbol mismatches at runtime.
- **Primary-header model:** declarations are emitted from the primary header
  you pass to the tool. Thin wrapper headers that only include another header
  can produce unexpectedly small output if the real declarations belong to the
  included file instead.

## Real-world examples

The repository includes worked examples and smoke programs for:

- SQLite: [examples/sqlite](examples/sqlite)
- Cairo: [examples/cairo](examples/cairo)
- libpng: [examples/libpng](examples/libpng)
- zlib: [examples/zlib](examples/zlib)

These examples do more than generate bindings: their `generate.sh` scripts also
build and run small functional tests to check the usability of the generated bindings.

The test suite also has end-to-end runtime coverage for:

- by-value records and enums
- callbacks and function-pointer returns
- globals and constants
- vectors and complex values
- atomic pointer-based APIs
- opaque forward declarations
- pointer-to-array and array-decay cases
- both `external_call` and `owned_dl_handle` link modes

See [tests/e2e/README.md](tests/e2e/README.md) for the current runtime case
matrix.

## Troubleshooting

### The generated module is empty or missing declarations

`mojo-bindgen` emits declarations from the primary header you pass in. If you
point it at a thin wrapper that only includes another header, Clang may
attribute declarations to the included header instead of the wrapper. In that
case, pass the real header directly.

### Parsing fails on project headers

Most parser failures are missing include paths, target flags, or defines. Add
the same flags your C build uses via repeated `--compile-arg`.

### Build succeeds but symbols are missing at runtime

Double-check:

- `--library` and `--link-name`
- your Mojo link flags for `external_call`
- your `--library-path-hint` for `owned_dl_handle`
- whether the original C declaration involved tricky `inline` or exotic layout that needs manual review.

## License

Licensed under the **MIT License**. See [LICENSE](LICENSE).

---

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

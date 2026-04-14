# mojo-bindgen

Generate **Mojo FFI** bindings from **C headers** using [libclang](https://pypi.org/project/libclang/) (Python bindings). The tool parses a header, builds an internal IR, and emits a `.mojo` module with `external_call` or `owned_dl_handle` linking.

For maintainer-facing architecture notes, see [docs/codegen-architecture.md](docs/codegen-architecture.md).

## Setup

### 1) System dependencies

Install `clang` and `libclang` first (required for header parsing):

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y clang libclang1

# Fedora
sudo dnf install -y clang llvm-libs

# macOS (Homebrew)
brew install llvm
```

If `libclang` is installed in a non-standard location, set `LIBCLANG_PATH` to the directory containing `libclang.so` / `libclang.dylib`.

### 2) Install project dependencies

From the repository root (requires [Pixi](https://pixi.sh)):

```bash
pixi install
pixi shell
```

This installs the `mojo-bindgen` package in editable mode and puts the `mojo-bindgen` CLI on your `PATH`.

You also need a **system libclang** shared library compatible with the `libclang` Python wheel.

## CLI

Emit Mojo FFI (default):

```bash
mojo-bindgen path/to/header.h -o bindings.mojo
```

Dump IR as JSON:

```bash
mojo-bindgen path/to/header.h --json -o unit.json
```

Extra clang flags (include paths, sysroot, target):

```bash
mojo-bindgen include/me.h --compile-arg=-I./include --compile-arg=--sysroot=/path/to/sysroot -o out.mojo
```

Set a specific C language standard:

```bash
mojo-bindgen include/me.h --compile-arg=-std=c99 -o out.mojo
```

`--compile-arg` standard flags accept `-std=...`, `--std=...`, and `std=...` forms. If no standard is provided, `-std=gnu11` is used by default.

By default, `--library` and `--link-name` are the header file stem (e.g. `me` for `me.h`). See `mojo-bindgen --help` for `--linking`, `--library-path-hint`, and other options.

## Limitations & Rough Edges

Parsing / IR:

- **Macros and constant expressions:** The parser only captures a small token-based subset of constant expressions. Simple integer, string, char, identifier-reference, and null-pointer forms are supported; multi-token arithmetic, `sizeof`, most casts, and function-like macros are skipped and emitted as comments in the mojo code.
- **Bitfields:** Basic bitfields are modeled, but some C edge cases are still lossy, especially mixed backing types and unusual layout-sensitive patterns.
- **Hard declaration shapes:** A few difficult C forms are still known parser/bindgen gaps, notably pointer-to-array declarations and anonymous nested struct/union combinations.
- **Anonymous and extension-heavy constructs:** The parser preserves more of these than before, but some compiler-extension or unusual anonymous record cases still degrade to `UnsupportedType` or require manual review.
- **C storage/linkage qualifiers:** Type qualifiers on pointers are preserved, but C declaration-level linkage/storage semantics such as `inline` / `extern inline` still are not modeled precisely enough to guarantee symbol availability.

Mojo lowering / runtime:

- **Variadic functions:** No thin callable wrapper is emitted; output is a comment noting that varargs are not modeled for FFI.
**Function pointers:** Function-pointer types are preserved in IR and lowered as opaque pointer ABI values in Mojo. Returned/parameter fnptr values can be passed through thin FFI, but callable wrappers for invoking function-pointer values are not generated yet; semantic signature comments are emitted where applicable (notably struct fields).
- **Globals:** Top-level globals are modeled in IR, but the emitter currently produces comment stubs rather than direct Mojo accessors, so these still require manual binding.
- **Non-`RegisterPassable` by-value returns:** Functions whose return types cannot be lowered through thin FFI are emitted as comment stubs rather than callable wrappers.
- **`inline` / non-standard linkage:** The generated bindings may still treat declarations as normal extern symbols even when C linkage rules are more subtle, which can produce symbol mismatches at runtime.

## Development

```bash
pixi run pytest
```

Build distributable artifacts through Pixi tasks:

```bash
pixi run clean-dist
pixi run build
```

Optional one-shot targets:

- `pixi run build-wheel`
- `pixi run build-sdist`

## License

See project files for license terms if applicable.

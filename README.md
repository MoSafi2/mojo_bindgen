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

- **Macros:** Only simple integer `#define` literals (name + one literal token) become constants. Float, string, multi-token, and expression macros are skipped.
- **Globals:** Non-`const` `extern` variables are not modeled; only top-level `const` variables with integer literal initializers may be captured similarly to macros.
- **Enums:** Underlying backing type is not always inferred correctly.
- **Bitfields:** Mixed backing types and wide bitfields produce wrong layouts; several edge cases are still lossy in the IR.
- **Pointer-to-array vs array-of-pointers** at file scope: some forms are not represented in IR at all.
- **Anonymous union inside struct:** Anonymous nested unions may not be captured as distinct union members.
- Qualifiers such as `inline`, `extern inline`, `volatile`, and `restrict` are currently stripped from the IR.

Mojo lowering / runtime:

- **Variadic functions:** No thin callable wrapper is emitted; output is a comment noting that varargs are not modeled for FFI.
- **Function pointers:** Fields and typedefs to function types are lowered to opaque pointers plus a comment describing the C signature.
- **`inline`:** May be emitted like a normal extern symbol; linkage and availability can differ from real C `inline` and may produce symbol mismatches.

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

# mojo-bindgen

Generate **Mojo FFI** bindings from **C headers** using [libclang](https://pypi.org/project/libclang/) (Python bindings). The tool parses a header, builds an internal IR, and emits a `.mojo` module with `external_call` or `owned_dl_handle` linking.

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

## Development

```bash
pixi run pytest
```

## License

See project files for license terms if applicable.

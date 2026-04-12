# mojo-bindgen

Generate **Mojo FFI** bindings from **C headers** using [libclang](https://pypi.org/project/libclang/) (Python bindings). The tool parses a header, builds an internal IR, and emits a `.mojo` module with `external_call` or `owned_dl_handle` linking.

## Setup

From the repository root (requires [Pixi](https://pixi.sh)):

```bash
pixi install
pixi shell
```

This installs the `mojo-bindgen` package in editable mode and puts the `mojo-bindgen` CLI on your `PATH`.

You also need a **system libclang** shared library compatible with the `libclang` Python wheel (often `libclang1` / `llvm` packages on Linux).

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

By default, `--library` and `--link-name` are the header file stem (e.g. `me` for `me.h`). See `mojo-bindgen --help` for `--linking`, `--library-path-hint`, and other options.

## Development

```bash
pixi run pytest
```

## License

See project files for license terms if applicable.

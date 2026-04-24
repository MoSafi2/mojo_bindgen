[![CI](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml/badge.svg)](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml)

# mojo-bindgen

> [!NOTE]
> Alpha stage: this project is under heavy development and may change quickly.

**C headers → Mojo FFI.** This tool uses [libclang](https://pypi.org/project/libclang/) to parse a primary C header, build an internal IR, and emit a `.mojo` module with `external_call` or `owned_dl_handle` linking—so you spend less time hand-writing glue and more time calling native code from Mojo.

**Requires Python 3.14+** and a **system `libclang`** compatible with the `libclang` Python wheel.

## Installation

### System dependencies

Install `clang` and `libclang` before installing the package (required for parsing):

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y clang libclang1

# Fedora
sudo dnf install -y clang llvm-libs

# macOS (Homebrew)
brew install llvm
```

If the shared library is not on the default loader path, set `LIBCLANG_PATH` to the directory containing `libclang.so` or `libclang.dylib`.

### Install from PyPI

```bash
pip install mojo-bindgen
```

See [mojo-bindgen on PyPI](https://pypi.org/project/mojo-bindgen/).

**Developing or contributing?** Clone setup, Pixi, virtualenvs, and checks are documented in [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick start

```bash
mojo-bindgen path/to/header.h -o bindings.mojo
```

Add include paths and other clang flags with repeated `--compile-arg` (for example `--compile-arg=-I./include`). If you omit a C standard, the parser defaults to `-std=gnu11`; use `--compile-arg=-std=c99` (or similar) to pin one. Run `mojo-bindgen --help` for every option.

## Python API

The CLI uses the same pipeline you can call from code:

```python
from pathlib import Path

from mojo_bindgen.codegen import MojoEmitOptions, generate_mojo
from mojo_bindgen.parsing.parser import ClangParser

unit = ClangParser(
    Path("include/mylib.h"),
    library="mylib",
    link_name="mylib",
    compile_args=["-I", "include"],
).run()
mojo_src = generate_mojo(unit, MojoEmitOptions(linking="external_call"))
```

Stable exports from the package root include `MojoGenerator`, `MojoEmitOptions`, `generate_mojo`, and `__version__`. Deeper codegen behavior is outlined in [docs/codegen-architecture.md](docs/codegen-architecture.md).

## Features at a glance

- **Parsing:** Primary C header + repeatable `--compile-arg` for include paths, sysroots, targets, and `-std=...`; defaults to `-std=gnu11`.
- **Type lowering:** C scalars, fixed-width typedef chains, pointers with const-aware mutability, fixed arrays, function pointers, complex values, vector extension types, and representable atomics are mapped cleanly to mojo code.
- **Records:** Structs with exact field layouts, synthetic padding, `@align` when Mojo can express it, bitfield storage/accessors, opaque byte-storage fallback are all represented.
- **Unions:** Eligible unions lower to `UnsafeUnion[...]` aliases; unsupported or ambiguous layouts fall back to byte `InlineArray` aliases with diagnostics.
- **Declarations:** Enums, typedefs, callback typedef aliases, object-like macros, constants, globals, and thin wrappers for non-variadic functions.
- **Linking:** `external_call` (default) or `owned_dl_handle` with optional `--library-path-hint`.
- **Globals:** `GlobalVar` / `GlobalConst` helpers for supported symbols; unsupported or unsafe cases become stubs or comments instead of silently emitting broken wrappers.
- **Runtime coverage:** E2E fixtures exercise records by value, callbacks, globals/constants, vectors, complex values, atomics, opaque handles, pointer-to-array cases, and both link modes.

## Not yet supported

Known gaps you may hit in generated code—verify critical layouts and symbols against your C toolchain.

- **Macros** Function-like macros and complex preprocessor behavior are not expanded into callable Mojo APIs; unsupported macros may appear as comments only.
- **Macros** Constant-expression support is limited to Literal arithmetic, common casts, enum/constants, `sizeof`, and some macro expressions.complex expressions can still become comments.
- **Variadic** functions do not get thin FFI wrappers; output notes that varargs are not modeled.
- **Atomics** are conservative: representable atomic fields suppress copy/register traits, and atomic globals are emitted as stubs.
- **Records** anonymous struacts/unions members are not auto-promoted to the parent record. anonymous records are treated the same as named member records with access syntax `outer.inner.member`
- difficult compiler extensions, difficult layouts, and subtle C **linkage / `inline`** rules may need manual fixes or can cause symbol mismatches at runtime.

## License

Licensed under the **MIT License**. See [LICENSE](LICENSE).

---

Architecture: [docs/codegen-architecture.md](docs/codegen-architecture.md) · Contributing: [CONTRIBUTING.md](CONTRIBUTING.md) · Security: [SECURITY.md](SECURITY.md) · Changelog: [CHANGELOG.md](CHANGELOG.md)

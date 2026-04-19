[![CI](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml/badge.svg)](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml)

# mojo-bindgen

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

- **Parsing:** Primary header + repeatable `--compile-arg` for includes, sysroot, target, and `-std=...`.
- **IR:** Structured IR with validation and reachability passes; **`--json`** dumps IR for debugging.
- **Mojo output:** Structs (with `@align` when expressible), unions (including `@unsafe_union` when eligible), enums, typedefs, and thin wrappers for non-variadic functions.
- **Linking:** `external_call` (default) or `owned_dl_handle` with optional `--library-path-hint`.
- **Globals:** `GlobalVar` / `GlobalConst` helpers where types are thin-FFI-compatible; unsupported cases become commented stubs.
- **Macros / constants:** Object-like macros and `const` initializers within a supported token grammar, with conservative folding; unsupported forms are often left as comments.
- **Tuning:** `MojoEmitOptions` exposes extra knobs beyond what the CLI exposes today.

## Not yet supported

Known gaps you may hit in generated code—verify critical layouts and symbols against your C toolchain.

- Function-like macros and many constant expressions (`sizeof`, most casts, etc.) are not fully modeled; unsupported macros may appear as comments only.
- **Variadic** functions: no thin FFI wrapper; output notes that varargs are not modeled.
- **Function pointers:** Carried as opaque pointer ABI; no generated wrappers to *call* through a fnptr value (signature comments may still appear).
- **Bitfields:** Emitted with layout metadata and warnings—cross-check ABI for exotic packing.
- **Globals:** No wrappers for atomics or types that cannot be lowered to a concrete Mojo surface type.
- **Struct-by-value returns:** Non–register-passable struct returns may become comment stubs instead of call wrappers.
- Difficult declarators, anonymous/extension-heavy records, and subtle C **linkage / `inline`** rules may need manual fixes or can cause symbol mismatches at runtime.

## License

Licensed under the **MIT License**. See [LICENSE](LICENSE).

---

Architecture: [docs/codegen-architecture.md](docs/codegen-architecture.md) · Contributing: [CONTRIBUTING.md](CONTRIBUTING.md) · Security: [SECURITY.md](SECURITY.md) · Changelog: [CHANGELOG.md](CHANGELOG.md)

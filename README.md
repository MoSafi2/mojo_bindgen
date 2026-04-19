[![CI](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml/badge.svg)](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml)

# mojo-bindgen

Generate **Mojo FFI** bindings from **C headers** using [libclang](https://pypi.org/project/libclang/) (Python bindings). The tool parses a header, builds an internal IR, and emits a `.mojo` module with `external_call` or `owned_dl_handle` linking.

**Requires Python 3.14+** (aligned with current Modular/Mojo Pixi stacks).

For maintainer-facing architecture notes, see [docs/codegen-architecture.md](docs/codegen-architecture.md). For contributing, security contact, and release notes, see [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [CHANGELOG.md](CHANGELOG.md).

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

The Pixi workspace is **linux-64 only** at the moment; on macOS or Windows use a virtual environment and `pip install -e ".[dev]"` instead (see [CONTRIBUTING.md](CONTRIBUTING.md)).

This installs the `mojo-bindgen` package in editable mode and puts the `mojo-bindgen` CLI on your `PATH`.

You also need a **system libclang** shared library compatible with the `libclang` Python wheel.

### Library usage (Python API)

The CLI wraps the same pipeline you can call from Python: parse a header to IR, then generate Mojo source.

```python
from pathlib import Path

from mojo_bindgen.codegen import MojoEmitOptions, generate_mojo
from mojo_bindgen.parsing.parser import ClangParser

header = Path("include/mylib.h")
unit = ClangParser(
    header,
    library="mylib",
    link_name="mylib",
    compile_args=["-I", "include"],
).run()
mojo_src = generate_mojo(unit, MojoEmitOptions(linking="external_call"))
```

Stable exports from the `mojo_bindgen` package root are `MojoGenerator`, `MojoEmitOptions`, `generate_mojo`, and `__version__`. Parsing types (`ClangParser`, `ParseError`, `Unit`) live in their modules and are treated as public for programmatic use; follow semver for the workflow above when upgrading.

## CLI

Inspect all options and examples:

```bash
mojo-bindgen --help
```

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

By default, `--library` and `--link-name` are the header file stem (e.g. `me` for `me.h`).
`--compile-arg` is repeatable, and `--emit-align` is enabled by default (`--no-emit-align` disables it).
Use `mojo-bindgen --help` for full option details.

## Features

- **libclang parsing:** Walks a primary C header with configurable compile flags (default language is `gnu11` if you do not pass `-std=...`). Repeatable `--compile-arg` passes include paths, sysroot, target triple, and standard selection.
- **IR and tooling:** Builds a structured IR, runs validation and a reachability materialization pass, and can **dump JSON** (`--json`) for debugging or downstream tools.
- **Generated Mojo surface:** Emits structs (with optional `@align` from C alignment via `--emit-align` / `--no-emit-align`), unions (including `@unsafe_union` when layout analysis marks them eligible), enums, typedefs, and thin wrappers for non-variadic functions using `external_call` or `OwnedDLHandle.call` depending on `--linking`.
- **Linking modes:** `external_call` (default) links C symbols at Mojo build time; `owned_dl_handle` resolves calls through `OwnedDLHandle`, with optional `--library-path-hint` for dlopen-style loading.
- **C globals:** For globals whose types are thin-FFI-compatible, the emitter generates `GlobalVar` / `GlobalConst` helpers that load and store through `UnsafePointer`, resolving symbols with `OwnedDLHandle.get_symbol` when needed (see `examples/global_consts/`). Atomics and layouts that cannot be lowered still become comment stubs with a short reason.
- **Macros and constants:** Object-like macros and `const` initializers are handled when the body fits the supported token expression grammar (literals, identifiers, parentheses, unary `-` / `~`, and binary operators); integer subexpressions are constant-folded when both operands are literals. Unsupported forms are classified and often preserved as comments rather than silent guesses.
- **Python API extras:** `MojoEmitOptions` also exposes pointer provenance (`ffi_origin`: `external` vs `any`), module header comments, and ABI reminder comments—tunable from code even though the CLI only exposes linking, library path hint, and align emission today.

## Limitations & Rough Edges

Parsing / IR:

- **Macros and constant expressions:** Function-like macros are not expanded into expressions. `sizeof`, most casts, and other constructs outside the supported token grammar are skipped or left as diagnostics; unsupported object-like macros may be emitted as comments only.
- **Bitfields:** Bitfields are modeled with width/offset metadata and emitted with layout comments and warnings to verify ABI against your C compiler; exotic packing or mixed backing-unit edge cases can still be wrong without cross-checking.
- **Hard declaration shapes:** A few difficult C declarator shapes and compiler-extension-heavy signatures may still require manual review, especially when mixed with unusual attributes or unsupported macro-driven spellings.
- **Anonymous and extension-heavy constructs:** Anonymous enums are emitted as top-level constants, and anonymous struct/union members are preserved as synthetic storage fields; some compiler-extension or unusual anonymous record cases still degrade to `UnsupportedType` or require manual review.
- **C storage/linkage qualifiers:** Type qualifiers on pointers are preserved, but C declaration-level linkage/storage semantics such as `inline` / `extern inline` still are not modeled precisely enough to guarantee symbol availability.

Mojo lowering / runtime:

- **Variadic functions:** No thin callable wrapper is emitted; output is a comment noting that varargs are not modeled for FFI.
- **Function pointers:** Function-pointer types are preserved in IR and lowered as opaque pointer ABI values in Mojo. Returned/parameter fnptr values can be passed through thin FFI, but callable wrappers for invoking function-pointer values are not generated yet; semantic signature comments are emitted where applicable (notably struct fields).
- **Globals:** Wrappers are not emitted for atomic globals or for types that cannot be lowered to a concrete Mojo surface type (see stub comments in generated output).
- **Non-`RegisterPassable` struct-by-value returns:** Functions that return a struct by value when that struct is not considered register-passable in the analysis pass are emitted as comment stubs rather than callable wrappers.
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

Licensed under the **MIT License**. See [LICENSE](LICENSE).

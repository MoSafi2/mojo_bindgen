[![CI](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml/badge.svg)](https://github.com/MoSafi2/mojo_bindgen/actions/workflows/ci.yml)

# mojo-bindgen

**C headers -> Mojo FFI.** `mojo-bindgen` parses real C with
[libclang](https://pypi.org/project/libclang/), and emits Mojo bindings for `external_call` or
`owned_dl_handle` workflows. this mirrors the spirit of `rust-bindgen` which follows the same approch for `Rust`

The goal is simple: make binding generation easy and faithful as possible to the
actual C surface, and fail conservatively when a declaration cannot be modeled
correctly.

## Implementation

The upcoming **0.4.0** release runs all parsing, analysis and generation in Mojo.
`mojo-bindgen` remains the single command, with a Python Typer/Rich facade for
help, completion and diagnostic presentation. The Mojo executable and importable
`mojo_bindgen` library are public interfaces. Python generation APIs have been
removed; the previous implementation is an optional reference under
[`legacy/python`](legacy/python/README.md).

## Requirements

- Linux x86-64 with x86-64-v3 instructions and glibc 2.35+
- Python 3.14+ for the CLI facade
- System C/C++ runtimes: `libstdc++.so.6` with `GLIBCXX_3.4.30` and `libgcc_s.so.1`
- Mojo **1.3.0.dev2026103105** for the generator and public Mojo API, installed
  as an exact package dependency
- Mojo **1.2.0** to compile the generated bindings in the tested configuration
- C development headers for the library being bound; system `clang` for
  `--dump-preprocessed` and a C toolchain for generated-code runtime checks

## Installation

### Install from PyPI

```bash
pip install mojo-bindgen --extra-index-url https://whl.modular.com/nightly/simple/
```

The 0.4 wheel declares `libclang==18.1.1` from PyPI and the exact `mojo-compiler`
nightly from Modular's index. It contains our executable, compiled Mojo package,
Clang resource headers and notices; LLVM/Clang and Mojo shared libraries come
from dependencies. The `clang` PyPI package alone does not supply libclang or a
compiler driver. Install system build tools when needed, for example
`sudo apt install build-essential clang` on Ubuntu.

The command above installs published releases. These 0.4 changes are not released
until a tagged release passes the distribution gates.

### Clean-system installation checks

The wheel is tested in a digest-pinned official Python 3.14 Debian 12 slim image,
without a host SDK or checkout mounted into the container. Python's slim image
already supplies glibc and the C/C++ runtime libraries listed above. Pip installs
Mojo, libclang and the CLI dependencies; no extra OS packages are needed to
generate bindings in either link mode from self-contained headers or Clang's
packaged builtin headers (`stdint.h`, `stddef.h`).

Additional inputs/features have separate prerequisites:

| Use | Additional Debian/Ubuntu package |
| --- | --- |
| Parse system C headers such as `stdio.h` | `libc6-dev` |
| Compile a public Mojo API consumer | `build-essential` |
| Use `--dump-preprocessed` | `clang` |

Third-party headers still come from the library being bound. Pip does not install
OS packages or arbitrary library development headers. Python itself is declared
through `Requires-Python: >=3.14`; the container test verifies pip rejects Python
3.13. See [the reproducible test](scripts/test_minimal_install.py).

### Install from Conda

The release includes a checksummed `mojo-bindgen-VERSION-channel.tar.gz` asset.
Extract it locally, then install `mojo-bindgen=VERSION` with Conda/Mamba from that
directory's `file://` channel plus `https://conda.modular.com/max-nightly/` and
`conda-forge`. The channel includes the pinned `libclang_mojo` artifact; Conda
resolves the compiler, Clang and Python facade dependencies normally.

### Install from source

```bash
git clone https://github.com/MoSafi2/mojo_bindgen
cd mojo_bindgen
mkdir -p mojo/build/test-tmp
pixi install --locked
pixi install --manifest-path mojo/pixi.toml --locked --all
pixi run --locked native-build
pixi run --locked mojo-bindgen --help
```

For development setup, checks, and Pixi workflows, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Public Mojo interfaces

`mojo-bindgen --print-mojo-path` prints the installed import directory. Compile
against it with the exact generator nightly:

```mojo
from mojo_bindgen import BindgenOptions, bindgen

def main() raises:
    var result = bindgen(BindgenOptions("input.h"))
    print(result.bindings_source)
```

The direct executable is `bin/mojo-bindgen` beside that `mojo/` directory. It
accepts the generation flags without the Python presentation layer. The Conda
package also installs the Mojo library on its compiler's normal import path.
For PyPI library clients, pass `-I` with the printed directory and configure
libclang as described in [the Mojo guide](mojo/README.md). Compiled `.mojoc`
modules require the exact compiler that produced them.

## Quick start

Generate bindings from a primary header:

```bash
mojo-bindgen path/to/header.h -o bindings.mojo --link-mode external-call
```

Pass common Clang inputs with structured flags:

```bash
mojo-bindgen include/mylib.h \
  -I ./include \
  -D MYLIB_FEATURE=1 \
  --std c11 \
  -o mylib_bindings.mojo
```

Add sibling public headers with repeated `--public-header`. The primary header
and public headers are included in an internal umbrella header. Transitive
`#include` files are parsed by Clang and can still contribute declarations
because source-file filtering is not applied yet:

```bash
mojo-bindgen include/mylib.h \
  --public-header include/mylib_extra.h \
  -I ./include \
  -o mylib_bindings.mojo
```

By default the parser uses `-std=gnu11` when no C standard is provided. Pin a
standard explicitly if your header requires one:

```bash
mojo-bindgen include/mylib.h --std c99 -o mylib_bindings.mojo
```

Use `--clang-arg` for raw Clang flags that do not have a structured option:

```bash
mojo-bindgen include/mylib.h --clang-arg=-fms-extensions -o mylib_bindings.mojo
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
mojo-bindgen include/mylib.h --link-mode external-call -o mylib_bindings.mojo

# runtime-loaded shared library
mojo-bindgen include/mylib.h \
  --link-mode owned-dl-handle \
  --library-path /usr/lib/libmylib.so \
  -o mylib_bindings_dl.mojo
```

## What works today?

`mojo-bindgen` evolves quickly, but it already supports a useful slice of real C
headers and is practical today as a starting point for generating bindings.

Current support includes:

- **Parsing and mapping:** real C parsing through `libclang`, repeatable `--clang-arg`
  support, and a structured IR pipeline rather than text-only generation.
- **Primitive types:** scalar types, typedef chains, pointers with const-aware
  mutability, fixed arrays, incomplete-array decay cases, complex values,
  vector extension types, and representable atomics.
- **Mojo-native numeric mapping:** vector types map to `SIMD[...]`, complex
  values map to `ComplexSIMD[...]`, and representable atomics map to
  `Atomic[...]`.
- **Records:** structs, anonymous members, mixed layouts that combine plain
  fields and bitfields, synthesized padding, and custom alignment emission
  where Mojo can represent the layout faithfully.
- **Bitfields:** bitfields are emitted through explicit storage fields plus
  synthesized getter and setter methods.
- **Unions:** eligible unions map to `UnsafeUnion[...]`; unions that cannot
  be represented safely fall back to opaque `Array[...]` storage with
  diagnostics to preserve layout.
- **Opaque and difficult layouts:** incomplete records, packed layouts, and
  alignment-sensitive record storages are preserved conservatively as opaque byte
  storage when a faithful typed layout is not possible.
- **Callbacks and function pointers:** callback typedefs, function-pointer
  fields, and function-pointer parameters and returns are preserved in Mojo via
  emitted `comptime` callback declarations and synthesized aliases when needed.
- **Functions:** thin wrappers are generated under both link modes. Dynamic calls
  use public, owner-borrowing `OwnedDLHandle` callables. Checked variadic wrappers
  are available in `external_call` mode.
- **Globals and constants:** because Mojo does not currently expose native C
  globals directly, supported globals map through generated `GlobalVar` /
  `GlobalConst` helper structs with synthesized `load()` / `store()` methods;
  constants and supported object-like macros map to `comptime` declarations.
- **Macros:** integer, float, string, and char literal macros, foldable macro
  chains, supported casts, and `sizeof(type)` expressions are emitted as Mojo
  code.
- **Debug IR output:** the CLI has hidden maintainer flags for serialized parser
  and Mojo IR sidecars. IR JSON follows the current implementation and is
  unversioned; snapshots must change with the schemas. See the
  [IR contracts](docs/ir_contracts.md) for stage boundaries and debug codecs.

## Current limitations

Known gaps you may still hit in generated code. For ABI-sensitive surfaces,
verify emitted layouts and symbols against your target toolchain.

- **Macros:** function-like macros, predefined macros, and more complex
  preprocessor behavior are preserved but usually emitted as comments for
  end-user review.
- **Variadics:** direct-call wrappers require exact declared types for the fixed
  prefix and explicitly promoted C types for the tail. Dynamic-mode variadics
  remain comment stubs because `OwnedDLHandle` has no variadic ABI metadata.
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
  some surfaces require manual handling. Bindings use `Atomic[T]`; incompatible
  atomic storage is opaque and is never silently treated as non-atomic storage.
- **By-value returns:** direct-link bindings use Mojo 1.2 C ABI declarations for
  eligible typed records containing fixed arrays. Packed, padded, explicitly
  aligned, bitfield, atomic, flexible-tail and opaque layouts remain conservative.
  Dynamic loading still requires `RegisterPassable` return types.
- **Linkage and compiler edge cases:** `inline`, compiler-specific linkage
  hints, and other extension-heavy cases can still require manual review and
  may lead to symbol mismatches at runtime.
- **Public-header model:** the primary header and any `--public-header` values
  are included in an internal umbrella header. Transitive `#include` files are
  also visible to Clang and may contribute declarations because source-file
  filtering is not applied yet.

## Real-world examples

The repository includes worked examples and smoke programs for:

- SQLite: [examples/sqlite](examples/sqlite)
- Cairo: [examples/cairo](examples/cairo)
- libpng: [examples/libpng](examples/libpng)
- zlib: [examples/zlib](examples/zlib)
- globals/constants: [examples/global_consts](examples/global_consts)

These examples do more than generate bindings: their `generate.sh` scripts also
build smoke artifacts or run small functional tests to check the usability of
the generated bindings. They pass `--layout-tests` explicitly when they need
layout-test sidecars.

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

`mojo-bindgen` parses the primary header plus any headers listed with
`--public-header` through an internal umbrella header. If a thin wrapper only
includes another header whose declarations you care about, pass that included
header with `--public-header` or use it as the primary header directly. Normal
transitive `#include` files are also visible to Clang and may appear in output.

### Parsing fails on project headers

Most parser failures are missing include paths, target flags, or defines. Add
the same flags your C build uses with `-I` / `--include`, `-D` / `--define`,
`-U` / `--undefine`, `--target`, `--sysroot`, `--std`, or repeated
`--clang-arg`.

### Debugging parser failures

Print the normalized Clang arguments that `mojo-bindgen` will use:

```bash
mojo-bindgen include/mylib.h -I ./include --print-clang-args
```

Write diagnostics as JSON while still generating normal output:

```bash
mojo-bindgen include/mylib.h \
  --diagnostics json \
  --diagnostics-output diagnostics.json \
  -o mylib_bindings.mojo
```

Dump the preprocessed input that Clang sees:

```bash
mojo-bindgen include/mylib.h \
  -I ./include \
  --dump-preprocessed mylib.preprocessed.c \
  -o mylib_bindings.mojo
```

### Build succeeds but symbols are missing at runtime

Double-check:

- `--library` and `--link-name`
- your Mojo link flags for `external_call`
- your `--library-path` for `owned_dl_handle`
- whether the original C declaration involved tricky `inline` or exotic layout that needs manual review.

## License

Licensed under the **MIT License**. See [LICENSE](LICENSE).

---

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

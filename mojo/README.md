# Native Mojo rewrite

The production generator lives in this directory. Both PyPI and Conda install
one `mojo-bindgen` product: a Python CLI facade, public Mojo executable and public
`mojo_bindgen` import library. The optional Python comparison implementation lives
under `legacy/python/` and is not shipped. See the root [installation guide](../README.md).

## Development

From the repository root:

```bash
mkdir -p mojo/build/test-tmp
pixi install --locked
pixi install --manifest-path mojo/pixi.toml --locked --all
pixi install --manifest-path examples/pixi.toml --locked
pixi run --locked native-build
pixi run --locked mojo-bindgen input.h -o bindings.mojo
pixi run --locked native-exec input.h -o direct.mojo
pixi run --locked native-test
pixi run --locked check-native
```

`native-build` writes `mojo/build/payload/bin/mojo-bindgen` and the compiled
packages under `mojo/build/payload/mojo/`. The facade and `native-exec` tasks select
the development SDK in child processes. Installed executables discover their
dependencies relative to their location. There is no second command or package name.

The manifest pins **Mojo 1.3.0.dev2026103105 (dc62ab6d)** on Linux x86-64.
Generated bindings are checked independently on **1.2.0** in `stable-tests`.
Never load a precompiled module from one compiler into the other. `format` and
`format-check` use the pinned SDK's `mblack`, one file per invocation.

## Installed interfaces

`mojo-bindgen --print-mojo-path` prints the public Mojo import directory. The
public executable is `$(dirname "$mojo_path")/bin/mojo-bindgen`, where `mojo_path`
is that directory. The normal PATH command is the Typer/Rich facade. Both use the
same generator, flags, diagnostic data and output algorithms.

The Conda package installs `mojo_bindgen.mojoc` on the compiler's default import
path. PyPI clients add `-I "$mojo_path"` when compiling against the exact nightly.
For a PyPI library client, point `MOJO_BINDGEN_CLANG_LIBRARY_PATH` at
`clang/native/libclang.so` in the installation's site-packages, and set
`MOJO_BINDGEN_CLANG_RESOURCE_DIR` to `$(dirname "$mojo_path")/lib/clang/18`.
The public executable configures these automatically. An explicitly supplied
`-resource-dir` Clang argument takes precedence.

```mojo
from mojo_bindgen import BindgenOptions, bindgen

def main() raises:
    var result = bindgen(BindgenOptions("input.h"))
    print(result.bindings_source)
```

## Library contracts

Import `CType`, `MojoType`, and payload structs from `mojo_bindgen.ir`, and use
`MapTypePass(TargetQueries(target_abi)).run(source)` or `map_type(source, queries)`.
For headers, import `BindgenOptions` and `bindgen` from `mojo_bindgen`; construct
`BindgenOptions("input.h")` and pass it to `bindgen`. The result contains raw CIR,
finalized MojoIR, binding source and optional layout source. Native emission
settings are grouped in `options.emit_options`. Parsing options and the parser
facade are also exported.

The package facade also exports `AnalysisOrchestrator`, `MojoEmitOptions`,
`render_mojo_module`, `render_layout_test_module`, and `generate_from_unit`.
`generate_from_unit(unit, emit_options, layout_module_name=String("bindings"))`
returns a `BackendResult` containing `normalized_unit`, `mojo_module`,
`bindings_source`, and optional `layout_test_source`. Parsing is not required for
this API. The module tree mirrors the Python backend's analysis, facts, mapping,
codegen, and layout-test boundaries.

- Closed native payload enums represent the two stages. The pinned compiler
  requires the `__enum` spelling; plain `enum` is rejected. Recursive enum types
  have explicit empty destructors to break lifecycle trait inference cycles.
- Recursive children use standard `ArcPointer`; nominal record references contain
  names and declaration keys, never owned record definitions. Callback parameters
  and parametric arguments remain stage-specific.
- Passes borrow inputs, inspect children through immutable pointer views, and
  construct fresh results. There is no mapping cache, interning, or type-node ID
  store. Mojo has no frozen dataclass equivalent: immutability is an API contract,
  not a claim that `ArcPointer` itself prevents mutation. Builders retain their
  own mutable collections and transfer or copy them on publication.
- Cycle validation examines all structural child edges. Shared acyclic children
  and nominal recursive records are valid. Deliberate low-level mutation is used
  only in the corruption/recovery test, and its ownership cycle is then broken.
- Borrowed matching avoids the consuming-match miscompilation recorded in the
  historical ledger. Lifecycle and unwind behavior are checked at both optimization
  levels. C pointer adaptation is confined to the frontend boundary; IR passes use
  no custom ownership wrappers.

The type, expression, declaration, and root debug codecs preserve the current
Python `kind`/`fields` JSON shape,
including defaults and nulls. Unknown fields/tags, wrong-stage children and invalid
field values are rejected. JSON is unversioned, for debugging/testing, and changes
with the model. Literal integers use exact canonical decimal digits; frontend folding uses
private exact arithmetic while published expression trees remain recursive.
Geometry/count fields use checked machine `Int`. Floating values use binary64,
including signed zero and Python debug JSON's nonfinite spellings. The private
parser rejects duplicate keys, malformed escapes and excessive nesting. No runtime
Python or EmberSerde reflection is used.

## Consuming Python debug JSON

Yes: load Python's `--dump-cir` output with `loads_cir` from `mojo_bindgen.serde`,
then call `generate_from_unit`. Load `--dump-mojo-ir` output with `loads_mojo_ir`
and print it with `render_mojo_module`. These are current-model debug formats,
not a versioned interchange API. Raw CIR needs generation options separately;
finalized MojoIR already contains its linking options and dependencies.

`pixi run --locked native-example-parity` provisions the independent locked
example-library environment and checks real zlib, Cairo, libpng, and SQLite CLI
dumps at O0/O3 in both linking modes. The native outputs are compared in full and
compiled/run on the stable SDK. See [the handoff guide and measured results](
../agent_docs/native_json_handoff.md) for direct file-driver commands and scope.

## Unicode support

The native normalizer uses stdlib UTF-8 strings, `Codepoint` iteration and `chr`.
On the pinned compiler, Unicode `isalnum`/`isdigit` equivalents are unavailable,
`Codepoint.is_python_space()` is narrower than Python's whitespace classification,
and `String.strip()` leaves U+2003 EM SPACE and U+00A0 NO-BREAK SPACE intact.

The generated name-classification and diagnostic-printability tables in `_unicode.mojo` preserve Python's Unicode
16.0.0 behavior without calling Python at runtime. The generator is development
only; regenerate after an intentional Unicode-data update, then format:

```bash
pixi run --locked python scripts/generate_native_unicode.py
pixi run --manifest-path mojo/pixi.toml --locked format
```

Parity tests cover every property-range transition, all ASCII codepoints, Unicode
whitespace, combining characters, supplementary-plane characters and both escaped
and literal UTF-8 JSON. Recheck stdlib support when upgrading the compiler.

Sources: [Codepoint API](https://mojolang.org/nightly/docs/std/collections/string/codepoint/Codepoint/),
[String implementation](https://github.com/modular/modular/blob/main/Mojo/stdlib/std/collections/string/string.mojo),
[EnumLike API](https://mojolang.org/docs/std/builtin/enum_like/EnumLike/).

## Local Conda packaging

```bash
pixi run --manifest-path mojo/pixi.toml --locked -e package package-render
pixi run --manifest-path mojo/pixi.toml --locked -e package package-build
```

The recipe builds one `mojo-bindgen` package from this checkout and tests its
installed facade, direct executable and public Mojo API outside the source tree.
Artifacts go under `mojo/build/conda`. The complete runtime requires glibc 2.35+
and x86-64-v3. `MOJO_BINDGEN_SOURCE_REVISION` renders immutable Git sources for
release builds; local builds use the checkout. Neither command uploads packages.

The wheel declares exact `mojo-compiler==1.3.0.dev2026103105` and
`libclang==18.1.1` dependencies. Use Modular's nightly extra wheel index for the
compiler. Conda maps these to its compiler/Clang packages instead; it does not
install pip's libclang into the same environment. LLVM and compiler shared
libraries are supplied by dependencies. Our payload keeps only the executable,
compiled Mojo modules, Clang resource headers and dependency notices.

The native manifest pins the shimless GitHub `libclang_mojo` build 1 and Clang 18.
It needs no sibling checkout or shim. The package recipe uses a checksum-verified
release channel prepared under ignored build artifacts. See the [frontend slice](
../agent_docs/native_frontend_plan.md) for dependency hashes and upstream fixes for unsaved-file ownership and uncapped
child traversal. Native parsing uses the upstream API directly.

See [the backend slice](../agent_docs/native_backend_plan.md),
[the staged roadmap](../agent_docs/native_mojo_roadmap.md) and
[historical evidence](../agent_docs/mojo_rewrite_results.md).


## Storage and C interoperability

Source floating formats and geometry are queried through Clang. Numeric types are
emitted only when the generated-binding toolchain has a matching representation.
Unsupported extended floats use aligned opaque storage; containing records keep
source size, alignment and stride. Unsafe by-value calls and callback signatures
become diagnostic stubs or opaque addresses. This does not implement extended
floating arithmetic or automatic C bridges.

Normalization expands padding into physical fields before printing and layout
reflection. Full-header layout checks include `max_align_t`, and
`large_alignment` is required to pass. The implementation contract and validation
are recorded in [the representation safety plan](../agent_docs/representation_safety.md).

Native acceptance now uses standard Mojo `TestSuite` programs and a standard-library
Python coordinator, independently of pytest/Python bindgen. Install the isolated
`stable-tests` environment for generated-binding checks. See the [native testing
contract](../agent_docs/native_testing.md) for parallelism, caches, selection and reports.

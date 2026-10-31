# Native Mojo rewrite

The native implementation lives beside Python and currently provides **recursive
type IR and pure type mapping**. C parsing, declaration/expression mapping, binding
emission, and the replacement Python wrapper are later stages. Use the existing
`mojo-bindgen` command to generate bindings.

## Development

From the repository root:

```bash
pixi install --manifest-path mojo/pixi.toml --locked
pixi run --locked native-build
pixi run --locked native-test
pixi run --locked native-parity
pixi run --locked check-native
```

`native-build` writes `mojo/build/mojo-bindgen-mojo` and
`mojo/build/mojo_bindgen.mojoc`. The command currently supports `--help` and
`--version`; it rejects header generation explicitly. Native unit tests compile
and run at O0 and O3. The parity harness builds an independent test driver at both
optimization levels and compares with the current Python implementation.

The native manifest and lock pin **Mojo 1.3.0.dev2026103105 (dc62ab6d)** on
Linux x86-64. The root environment retains its existing stable compiler for Python
and generated-binding tests. Never load a precompiled package from one compiler
into the other. Native test subprocesses put the nightly runtime library directory
first so an activated stable environment cannot select its runtime accidentally.

Formatting uses the SDK's `mblack`, one file per invocation; this is the formatter
behind `mojo format` and also supports a non-mutating `--check` mode:

```bash
pixi run --manifest-path mojo/pixi.toml --locked format
pixi run --manifest-path mojo/pixi.toml --locked format-check
```

## Library contracts

Import `CType`, `MojoType`, and payload structs from `mojo_bindgen.ir`, and use
`MapTypePass(TargetQueries(target_abi)).run(source)` or `map_type(source, queries)`.
The package facade exports the type families and mapping entry points as well.

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
  levels; no unchecked origin casts or custom ownership wrappers are used.

The type debug codecs preserve the current Python `kind`/`fields` JSON shape,
including defaults and nulls. Unknown fields/tags, wrong-stage children and invalid
field values are rejected. JSON is unversioned, for debugging/testing, and changes
with the model. The private JSON parser handles precisely the integer-valued type
schema; it is not a general floating-point JSON library. Geometry/count fields use
machine `Int`; out-of-range numbers fail rather than truncate. It rejects duplicate
keys, malformed escapes and excessive nesting. No runtime Python or EmberSerde
reflection is used. Full-unit/expression codecs belong to the backend stage.

## Unicode support

The native normalizer uses stdlib UTF-8 strings, `Codepoint` iteration and `chr`.
On the pinned compiler, Unicode `isalnum`/`isdigit` equivalents are unavailable,
`Codepoint.is_python_space()` is narrower than Python's whitespace classification,
and `String.strip()` leaves U+2003 EM SPACE and U+00A0 NO-BREAK SPACE intact.

The small generated property tables in `_unicode.mojo` preserve Python's Unicode
17.0.0 behavior without calling Python at runtime. The generator is development
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

The development recipe builds the executable and precompiled import package from
this checkout and tests their installed form outside the source tree. Artifacts
are written under `mojo/build/conda`. The development CLI package declares glibc
2.34 or newer, matching its inspected ELF symbol requirements. Nothing is uploaded. A publishing recipe must
replace the development source path with an immutable Git revision; distribution
remains a later milestone. The exact compiler pin applies to build, host, and run
requirements because `.mojoc` is compiler-specific. The compiler package currently
brings Python tooling transitively; bindgen's native implementation does not call it.

`libclang_mojo`, libclang, and its shim are intentionally absent from this slice.
Before the frontend stage, publish/pin the sibling wrapper's compatibility fixes
and validate them against this compiler; do not depend on an uncommitted sibling
checkout.

See [the staged roadmap](../agent_docs/native_mojo_roadmap.md) and
[historical evidence](../agent_docs/mojo_rewrite_results.md).

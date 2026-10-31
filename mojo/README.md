# Native Mojo rewrite

The native implementation lives beside Python and provides a **complete backend
from constructed CIR**: validation, canonicalization, analysis, mapping, target
normalization, bindings, and layout-test source. Direct C parsing and the replacement
Python wrapper are later stages. Use the existing `mojo-bindgen` command for headers.

## Development

From the repository root:

```bash
pixi install --manifest-path mojo/pixi.toml --locked
pixi run --locked native-build
pixi run --locked native-test
pixi run --locked native-parity
pixi run --locked native-example-parity
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
  levels; no unchecked origin casts or custom ownership wrappers are used.

The type, expression, declaration, and root debug codecs preserve the current
Python `kind`/`fields` JSON shape,
including defaults and nulls. Unknown fields/tags, wrong-stage children and invalid
field values are rejected. JSON is unversioned, for debugging/testing, and changes
with the model. Literal integers use exact canonical decimal digits; arithmetic
remains symbolic.
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

See [the backend slice](../agent_docs/native_backend_plan.md),
[the staged roadmap](../agent_docs/native_mojo_roadmap.md) and
[historical evidence](../agent_docs/mojo_rewrite_results.md).


## Preserved layout-test limitations

Full-header parity intentionally preserves two Python-backend limitations found
by the new runtime checks. On this host, system `max_align_t` contains a 16-byte
`long double`, which currently maps to an 8-byte target type. Also, a padding IR
member can print multiple scalar fields while the layout-test generator counts it
as one field, giving an incorrect reflected index for a following field.

The `large_alignment` fixture records the latter failure explicitly. Native
binding runtime checks still run in both modes; passing layout runtime checks cover
other fixture records. The runtime fixtures omit the unrelated system
`max_align_t` declaration, while full-header intermediate and byte comparisons
include it. Fixing these behaviors requires a coordinated Python/native change;
this rewrite preserves the existing output contract.

# Slice 3: native frontend and CLI

## Contract and dependency provenance

The native implementation runs headers through libclang, recursive CIR, the
existing backend, and generated binding/layout source without invoking Python.
Python remains the canonical `mojo-bindgen` command and differential reference;
native development uses `mojo-bindgen-mojo`. No default switch or publication.

- Native compiler remains `1.3.0.dev2026103105`, Linux x86-64; generated-binding
  acceptance uses the separate root stable compiler.
- GitHub package: `libclang_mojo 0.3.0.dev20261031`, build
  `mojo1_3_0_dev2026103105_linux_64_1`.
- Package SHA-256:
  `4f3399db303c6f82b5a5df07fa27c255e15f8b3a2bce0a013bfc439c4ee4063c`.
- Release-channel archive SHA-256:
  `4fc36b8f450c8286792699c1d2090d52645c12f115d2145983e8003d3b539d19`.
- Upstream metadata revision: `b08f435189c2e515b66b0b53e63a4de753b17849`;
  producing source: `e1885cf9a558439e62478cfa07c2929db9594519`.
- Upstream replaced assets and moved the prerelease tag. The explicit URL/hash
  and native lock are authoritative. Neither the sibling checkout nor a native
  shim is a dependency. Pixi >=0.80 is required.

Sources: [release](https://github.com/MoSafi2/mojo_libclang/releases/tag/v0.3.0-dev.20261031),
[consumer manifest](https://github.com/MoSafi2/mojo_libclang/blob/b08f435189c2e515b66b0b53e63a4de753b17849/packaging/consumers/v0.3.0-dev.20261031/pixi.toml),
[recipe](https://github.com/MoSafi2/mojo_libclang/blob/b08f435189c2e515b66b0b53e63a4de753b17849/packaging/modular-community/libclang_mojo/recipe.yaml).

## Implemented architecture

`parsing/` mirrors Python's frontend, registry, target ABI, comments, and lowering
boundaries. Lowering passes explicitly borrow one private mutable record registry;
there is no mutually owning callback/service graph. Declared/building/completed
states support nominal recursion, transactional publication, and rollback.
Published IR contains owned source facts and standard ARC children, no Clang
handles or flat type-node storage. Anonymous identities retain Python's SHA-256
policy. Fact caches are per parse configuration; mapped results remain uncached.

Types retain source geometry/qualifiers, callbacks, arrays, atomics, vectors,
complex and unsupported categories. Constant parsing preserves source float
spelling and supports casts, sizeof, strings/escapes, ternaries, and integer
operators. Exact folding uses temporary signed-magnitude UInt32 limbs; published
integers retain canonical decimal strings. Current Python semantics, including
modulo behavior and unsupported expressions, are preserved. Source macros retain
order/classification, folded references, and opt-in Clang fallback. Object-like
expansion utilities retain the 10,000-invocation limit and recursion suppression.

`BindgenOptions`, `ClangOptions`, `ClangParser`, `BindgenOrchestrator`, `bindgen`,
and `BindgenResult` provide header generation. Emission options live together in
native `BindgenOptions.emit_options`. `BindgenResult.unit` is raw CIR; the existing
`generate_from_unit` backend API is unchanged. CLI flags cover public headers,
Clang configuration, both linking modes, comments, diagnostics, warning exits,
preprocessing and CIR/MojoIR dumps. JSON remains unversioned debug/test data.
The complete pipeline succeeds before binding/debug output publication.

Both implementations query calling conventions and reject unsupported non-default
conventions in unit validation and direct callback mapping. Ordinary platform-C
conventions normalize to the previous default, preserving ordinary output.

## Localized compatibility constraints

1. **Unsaved-file owner lifetime.** Build 1's `Index.parse` extracts untracked
   pointers from its local `UnsavedFileArena`, whose destructor can run before the
   C call. A direct unsaved-only header failed to parse; inspecting an arena after
   its last borrow exposed freed strings. `parsing/_compat.mojo` borrows the arena
   across the raw parse call and owns argument buffers through `finally`. It
   returns the normal high-level TranslationUnit. Remove this adapter after an
   upstream lifetime fix passes the O0/O3 regression. No shim or vendoring.
2. **Traversal limit.** Upstream's iterator silently truncates above 4,096 immediate
   children. Native parsing exclusively uses checked `children()` and reports the
   capacity failure. Overflow is tested. Removing the upstream limit is outside
   this slice; supported corpus/example inputs must pass without reaching it.
3. **Paths/processes.** The pinned stdlib lacks path canonicalization and a checked
   argv subprocess capture API. Linux realpath uses caller-owned PATH_MAX storage;
   compiler subprocess arguments are shell-quoted, status is checked, stdout bytes
   and trailing newlines are retained. Raw C pointer adaptation stays here.
4. **Unsigned enum values.** The high-level wrapper returns Int for unsigned C
   values; adapt the preserved UInt64 bits before decimal conversion.

Keep existing backend layout limitations documented in `native_backend_plan.md`.
Do not fix them incidentally or loosen parity assertions to hide them.

## Acceptance

- Existing Python checks remain required. Native unit tests run at O0/O3.
- The separate-process Python frontend reference loads the exact native package's
  libclang runtime before any Clang use. Arguments/include ordering must also
  match; mixing GCC and Clang resource-header ordering changes real CIR.
- 49 shared headers compare raw CIR, finalized MojoIR, binding and layout source
  in both link modes and at O0/O3. Existing intermediate backend parity stays on.
- Native headers for zlib/Cairo/libpng/SQLite compare against Python, then generated
  bindings compile/run on stable. Existing Python-JSON handoffs remain tested.
- Dedicated tests cover keepalive, registry publication/rollback, child overflow,
  wide folding, Unicode paths/names, unsigned enums, targets/char policy, CLI
  diagnostics/options/errors, debug dumps, and ABI rejection without output.
- Conda builds verify the upstream channel checksum, install named exact package
  dependencies, and test CLI/API generation outside the source checkout. No
  package uploads. Compiler/runtime dependencies stay exact.

## Final validation (2026-11-01, Linux x86-64)

- Full suite: **506 passed** in 249.66 seconds, including native/Python parity,
  generated-binding compilation/runtime on stable, and existing Python gates.
- Light gate: format, Ruff and Pyright pass; **400 passed, 106 deselected**.
- Native tests: **18 tests at O0 and O3**, 36 successful executions. Native
  precompilation, executable build and formatting checks pass.
- Direct native frontend: 49 shared headers in both modes at both optimization
  levels, with exact raw CIR, semantic MojoIR and byte-identical binding/layout
  source. Additional target/Unicode/enum/bitfield/CLI/error cases pass.
- Exact arithmetic: **682 constructed unary/binary folding comparisons per
  optimization**, including large signed values and invalid operations.
- Examples: zlib, Cairo, libpng and SQLite pass direct native generation and the
  retained Python-JSON handoffs, both modes and O0/O3. All **32 example cases**
  compile/run their generated bindings on stable; layout sources compare exactly.
- The local Conda package builds and passes installed compiled Mojo API and CLI
  header generation outside the checkout. The pinned upstream module/runtime is
  resolved without a sibling checkout or shim; nothing was published.

Temporary-storage quota failures interrupted initial local test/package attempts.
The completed full suite ran with scratch under the ignored build directory.
Package scripts explicitly set compiler scratch inside isolated build/test scripts
as well as the outer package runner; the final package build and tests passed.

The historical experiment ledger, completed Python refactor plan, root stable lock
and generated source goldens are unchanged. The documented child-count limit and
existing backend layout-test limitations remain explicit acceptance boundaries.

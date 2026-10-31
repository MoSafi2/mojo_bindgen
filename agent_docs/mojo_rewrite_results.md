# Mojo rewrite: results ledger for coding agents

Recorded on **2026-10-31**, Linux x86-64. This consolidates the research,
experiments, selected direction and implementation pointers. The experiment code,
test harnesses, raw reports, binaries and isolated nightly environment were removed
at the user's request. Results below describe the work performed before cleanup;
they are not claims about later compilers or tests still present in this checkout.

## Selected direction

- Keep type expressions recursive, using closed payload enums and ordinary structs.
  **Do not use flat type-node storage or numeric type handles.**
- Use separate CIR and MojoIR families, including distinct pointer and callback
  payloads. Mapping borrows CIR and constructs MojoIR.
- Prefer standard `ArcPointer` children when passes retain/share types; use
  `OwnedPointer` for genuinely unique ownership. Keep parsed structure in runtime
  fields rather than encoding each input subtree in generic parameters.
- Represent recursive records and forward declarations through named declaration
  references and a symbol table. A `Node*` contains a pointer to a reference to
  `Node`; it does not own the record's field definitions recursively. Preserve
  existing qualified names and stable declaration keys at compatibility boundaries.
- Give recursive enums an explicit empty `__deinit__(deinit self)` in the tested
  toolchains. This breaks lifecycle inference cycles; normal field destruction
  still runs. Borrow enum payloads during matching.
- Keep pass state and ABI queries explicit and scoped to one input. Preserve the
  existing CLI, emitted bindings and JSON contracts during Python refactoring.

`ArcPointer` provides shared ownership, not automatic immutability. Use its
immutable `ptr()` view in analysis, keep builder/mutation APIs separate, and expose
read-only input APIs. Copying an ARC handle shares its pointee; copying an enum by
value may still copy owned strings or lists. Reference counting does not collect
ownership cycles, so nominal declaration back-references must not become strong
structural child links.

## Toolchains and compiler results

| Toolchain | Exact version checked |
| --- | --- |
| Stable | Mojo **1.2.0**, compiler `2016d0cd` |
| Nightly | Mojo **1.3.0.dev2026103105**, compiler `dc62ab6d` |

The nightly was isolated from the main Pixi environment, using
`https://conda.modular.com/max-nightly/` and `conda-forge`, with the exact Mojo
version pinned. Its manifest, lockfile and installed environment were removed.

| Experiment | Stable result | Pinned nightly result |
| --- | --- | --- |
| Recursive owned/ARC enums with explicit empty destructors | Pass at O0/O3 | Pass at O0/O3 |
| Counted resource destruction, moves, last shared owner and exception unwind | Pass at O0/O3 | Pass at O0/O3 |
| Recursive scalar/array/pointer traversal, fresh-output mapping and rendering | Pass at O0/O3 | Pass at O0/O3 |
| Bindgen-shaped recursive payload structs across ten CIR family shapes, including callback parameter lists, optional canonical references and copying | Pass at O0/O3 | Pass at O0/O3 |
| Separate CIR/MojoIR with named record references, a symbol table, immutable pointer views, repeated mapping and unknown-symbol handling | Pass at O0/O3 | Pass at O0/O3 |
| EmberJson-shaped `Variant[Int, List[Value]]`, including independent deep copies | Pass at O0/O3 | Pass at O0/O3 |
| Heterogeneous enum payloads; borrowed matching; tuple payloads, guards, reference binding and matching values obtained from a list | Pass | Pass |

Five positive programs supplied **ten O0/O3 build-run checks per compiler**. These
covered lifecycle, recursive values, the small mapping slice, the payload catalog
and the named-record example. The named-record example was independently rebuilt
and executed on both compilers at both optimization levels immediately before
cleanup: all four checks passed.

The examples establish feasibility and ownership behavior, not a complete native
generator or full recursive-mapper equivalence. The catalog exercised family
shapes; it did not implement every field's production mapping policy.

### Failures and limitations worth retaining

| Case | Observation |
| --- | --- |
| Recursive owned enum relying on synthesized destruction | Trait inference rejected it on both compilers; the explicit lifecycle hook resolved the tested smart-pointer shape. |
| Recursive ARC enum relying on synthesized destruction | Passed on stable; rejected as non-`Deinitable` on nightly. Explicit destruction resolved the tested shape on both. |
| Recursive `Variant[Leaf, Child]` with smart-pointer indirection and fieldwise construction | Rejected by trait/construction inference on both. Do not generalize the working recursive `Variant`/`List` shape to arbitrary payload arrangements. |
| Copyable enum containing a direct `List[Node]` case | Rejected on both, including with an explicit empty destructor. The selected representation uses smart-pointer child indirection. |
| Consuming match with `case .owned(var payload)` on a moved enum holding `OwnedPointer[Int]` | Stable rejected it. Nightly compiled the O0 reproducer, but it returned 0 instead of 7 and failed its assertion. A separate manual O3 run segfaulted. Compilation alone did not establish correctness. |
| Plain `enum` spelling | Rejected on both tested compilers; successful examples used `__enum`. Treat this as a pinned language dependency rather than proof of public stabilization. |

Recheck these against the compiler selected for implementation. Borrowed matching
plus fresh output worked without the consuming-match path. No unchecked origin
casts, custom allocator, raw-pointer storage or runtime Python were needed in the
selected native examples.

## Historical differential comparison

A superseded flat-ID pilot agreed with the production Python mapper for **56
hand-built inputs and 51 parsed fixture type slots**, represented by **185 CIR
nodes**, at O0/O3 on both compilers. Its isolated pytest suite had **64 passing
tests**. That code and its tests have been removed; this was comparison evidence,
not the chosen representation and not full recursive-implementation acceptance.

Coverage included every production CIR type family, scalar families, qualifiers,
all array shapes, ABI-dependent char mapping, supported/opaque atomics, vectors,
complex types, unsupported types, callback names/conventions, sharing and nested
callbacks. Checks also covered occurrence preorder versus unique traversal,
structural-cycle detection, error cleanup, repeated mapping and independent sessions.

Preserve these behavioral checks when implementing the recursive version. The
former native pilot intentionally accepted only ASCII identifiers, whereas the
production Python normalizer handles Unicode. That restriction must not silently
become the final generator's behavior. Small executable timings were dominated by
startup and printing; they did not establish a throughput or storage-performance
winner.

## Type topology observations

The profile counted existing Python object identities, structural child edges and
expanded occurrences. It did not perform structural interning or measure cache
hits, retained memory or runtime performance.

| Cohort | Root type slots | Distinct nodes | Reused identities | Maximum depth |
| --- | --- | --- | --- | --- |
| Hand-built pilot inputs | 56 | 69 | 2 | 3 |
| Parsed pilot slots | 51 | 116 | 0 | 5 |
| Combined pilot | 107 | 185 | 2 | 5 |
| 18 corpus/stress/example headers, per-header counts summed | 1,738 | 3,393 | 1 | 7 |
| SQLite, included in the preceding row | 686 | 1,788 | 0 | 7 |

No structural ownership cycles were found in these profiles. Expanding every
root/child occurrence in the 18-header cohort gave 3,394 nodes; that cohort contained
679 nominal reference nodes. It included all non-macro declaration slots returned
by the local parser, including included declarations. The smaller parsed pilot
filtered declarations to fixture names. Nominal declaration graphs can still be
recursive; no-cycle observations here concern structural type ownership only.

The broader cohort was the 14 headers under `tests/corpus/headers/`, the three
`tests/stress/fixtures/*/input.h` headers and `examples/sqlite/sqlite3.h`. These
observations support preserving nested types without establishing that future
inputs cannot share nodes.

## Ecosystem prior art and source pointers

The links below encode the full inspected revisions. Findings are source-backed;
only the explicitly listed executable subsets were tested.

### EmberJson — recursive values and owner/view boundaries

Inspected **`e7feca8ebbdf2a338f586fed737bf8d01e6cad05`**.

- [Value lifecycle hook](https://github.com/bgreni/EmberJson/blob/e7feca8ebbdf2a338f586fed737bf8d01e6cad05/emberjson/value.mojo#L88-L102): explicit empty destruction for mutually recursive values. This supplied the technique that resolved our smart-pointer enum inference failures.
- [Document and DocValue](https://github.com/bgreni/EmberJson/blob/e7feca8ebbdf2a338f586fed737bf8d01e6cad05/emberjson/document.mojo#L29-L109): immutable data ownership and origin-tracked borrowed views, with explicit materialization of an independent mutable value. Consult the ownership boundary; its flat JSON tape is not the selected type representation.
- [Dependency manifest](https://github.com/bgreni/EmberJson/blob/e7feca8ebbdf2a338f586fed737bf8d01e6cad05/pixi.toml): declared Mojo `>=1.2.0.dev2026092805,<2`, and pinned EmberSerde `8a5cde9bb7e838cf1e8e6b753c5594ed612f2aa9`. The full package build was not tested here.

### EmberSerde — compile-time reflection and safe construction

Inspected **`cb91a0b7cdebb9c005bc8b8341f8d49ab96f09b1`**, declaring Mojo **1.2.0**.

- [Serialization dispatch](https://github.com/bgreni/EmberSerde/blob/cb91a0b7cdebb9c005bc8b8341f8d49ab96f09b1/emberserde/serialize/impls.mojo#L216-L228): custom trait implementations with compile-time reflection for ordinary structs. Field type/index metadata can remain static; runtime Python introspection is unnecessary.
- [Struct construction and error handling](https://github.com/bgreni/EmberSerde/blob/cb91a0b7cdebb9c005bc8b8341f8d49ab96f09b1/emberserde/deserialize/__init__.mojo#L459-L558): initialize `Defaultable` targets before filling fields, track seen fields and annotate error paths. Prefer fully initialized wire structs or staged constructors over its compiler-internal initialization fallback.
- [Variant wire tags](https://github.com/bgreni/EmberSerde/blob/cb91a0b7cdebb9c005bc8b8341f8d49ab96f09b1/emberserde/serialize/impls.mojo#L58-L73) and [tag naming](https://github.com/bgreni/EmberSerde/blob/cb91a0b7cdebb9c005bc8b8341f8d49ab96f09b1/emberserde/struct_modifiers.mojo#L68-L85): externally tagged `Variant` output needs an adapter for bindgen's existing `kind` encoding, omissions, defaults and renamed fields. Support for `Variant` does not establish serde support for `__enum`.
- [BorrowingDeserializer](https://github.com/bgreni/EmberSerde/blob/cb91a0b7cdebb9c005bc8b8341f8d49ab96f09b1/emberserde/deserialize/borrow.mojo#L42-L85): the erased/re-attached origin correspondence is explicitly unchecked. Prefer concrete origin-parameterized APIs where possible.

Unmodified upstream test subsets produced:

| Subset | Stable | Pinned nightly |
| --- | --- | --- |
| `serialize/test_struct.mojo` and `serialize/test_enum.mojo` | 15 passed | 15 passed |
| `deserialize/test_struct.mojo`, `deserialize/test_enum.mojo`, `deserialize/test_struct_modifers.mojo` | 31 passed | All three files failed to compile |

Nightly rejected `return result^` in `deserialize/impls.mojo:474`, reporting that
generic `Tuple[*Ts]` did not conform to `Movable`. This happened during import,
before the selected deserialization tests executed. No upstream patch or new
production dependency was introduced.

### Marrow — runtime representations and honest trait boundaries

Inspected **`3462b909adf84e8d17f9cec17487f959d4b7c463`**, declaring Mojo
**1.2.0.dev2026101905** and matching dependency forks. This review was source-only.

- [Runtime expression representation](https://github.com/kszucs/marrow/blob/3462b909adf84e8d17f9cec17487f959d4b7c463/marrow/expr/runtime/values.mojo#L4-L35) and [RuntimeValue](https://github.com/kszucs/marrow/blob/3462b909adf84e8d17f9cec17487f959d4b7c463/marrow/expr/runtime/values.mojo#L237-L260): put input-dependent structure in fields. Runtime wrappers should not promise compile-time associated members they cannot supply.
- [DynType](https://github.com/kszucs/marrow/blob/3462b909adf84e8d17f9cec17487f959d4b7c463/marrow/dtypes.mojo#L972-L994) and [DynArray](https://github.com/kszucs/marrow/blob/3462b909adf84e8d17f9cec17487f959d4b7c463/marrow/arrays.mojo#L3292-L3388): closed payload families, removal of unsuitable trait conformances, and an explicit recursive lifecycle hook. Some comments describe older designs; inspect actual declarations.
- [UniqueVariant, SharedVariant and visitor helpers](https://github.com/kszucs/marrow/blob/3462b909adf84e8d17f9cec17487f959d4b7c463/marrow/utils/enum.mojo#L86-L337): distinguish value copying from shared ownership. The generic proofs, casts, closure workarounds and origin widening are not needed merely to dispatch bindgen's small closed families; start with borrowed enum matches.

### rust-bindgen — parsing phases and semantic references

Inspected **`bb8bd1b0211752477707f0084f92c2af526eba89`**. Consult the generator's
internal model without adopting its flat storage:

- [TypeKind](https://github.com/rust-lang/rust-bindgen/blob/bb8bd1b0211752477707f0084f92c2af526eba89/bindgen/ir/ty.rs#L605) and [FunctionSig](https://github.com/rust-lang/rust-bindgen/blob/bb8bd1b0211752477707f0084f92c2af526eba89/bindgen/ir/function.rs#L270): closed payload families, alias identity and ordered callback signatures.
- [Partial parsing and later resolution](https://github.com/rust-lang/rust-bindgen/blob/bb8bd1b0211752477707f0084f92c2af526eba89/bindgen/ir/context.rs#L649): register declarations before descending and resolve nominal references in an explicit phase. Avoid creating strong ownership cycles.
- [Traversal](https://github.com/rust-lang/rust-bindgen/blob/bb8bd1b0211752477707f0084f92c2af526eba89/bindgen/ir/traversal.rs#L351) and [worklist analysis](https://github.com/rust-lang/rust-bindgen/blob/bb8bd1b0211752477707f0084f92c2af526eba89/bindgen/ir/analysis/mod.rs#L81): distinguish occurrence traversal from unique-graph traversal, and keep analysis facts outside payloads. Introduce fixpoint analysis only where needed.
- [Temporarily loaning an item](https://github.com/rust-lang/rust-bindgen/blob/bb8bd1b0211752477707f0084f92c2af526eba89/bindgen/ir/context.rs#L973): a Rust-specific borrowing accommodation. Prefer immutable input and separately owned output rather than porting this mutation scheme.

### Mojo documentation to recheck

[ArcPointer and immutable views](https://mojolang.org/docs/std/memory/arc_pointer/ArcPointer/),
[OwnedPointer](https://mojolang.org/docs/std/memory/owned_pointer/OwnedPointer/),
[Variant](https://mojolang.org/docs/std/utils/variant/Variant/),
[EnumLike](https://mojolang.org/docs/std/builtin/enum_like/EnumLike/),
[nightly release notes](https://mojolang.org/releases/nightly/), and
[stability guidance](https://mojolang.org/nightly/docs/api-docs/stability/).

## libclang wrapper compatibility result

The sibling `../mojo_libclang` was upgraded for Mojo **1.2.0 / libclang 18**;
that independent compatibility work is retained. Its generated bindings used
mojo-bindgen revision `ad2ae77898a738ac88d7d4b9b4d87ca96e874790`.
Validation passed **412 native tests in 19 files**, including **37 layout tests**.
A rebuilt local package also parsed the shared frontend fixture consistently with
Python: `Node` size/alignment 16/8; `consume` had three parameters and a four-byte
return type. This was Linux x86-64 validation, not other-platform or publication
acceptance.

Relevant fixes updated removed names, explicit origins and lifecycle syntax,
retaining ARC owners until foreign diagnostic/translation-unit disposal completed.
When validating against a separate libclang provider, put the active Mojo runtime
library directory ahead of the provider's libraries to avoid runtime mismatches.
Consult the sibling's `clang/`, `test/`, `pixi.toml` and package-build scripts.
Its eventual package source revision must identify the upgraded wrapper before
publishing. Cleanup of these experiments did not revert the sibling changes.

## Repository pointers and implementation acceptance

- [IR schemas](../mojo_bindgen/ir.py), [type lowering](../mojo_bindgen/parsing/lowering/type_lowering.py), [type mapping](../mojo_bindgen/analysis/mojo/type_mapping.py), [declaration mapping/session](../mojo_bindgen/analysis/mojo/decl_mapping.py), and [traversal](../mojo_bindgen/analysis/type_walk.py).
- [CIR canonicalization](../mojo_bindgen/analysis/cir/cir_canonicalizer.py) and [MojoIR normalization](../mojo_bindgen/codegen/normalize_mojo_module.py) show the replacement-style passes to preserve.
- [Serialization contracts](../mojo_bindgen/serde.py), [CIR JSON roundtrips](../tests/unit/test_ir_json_roundtrip.py), [MojoIR JSON roundtrips](../tests/unit/test_mojo_ir_json_roundtrip.py), [type mapping tests](../tests/unit/test_analysis_type_mapping.py), and [walk tests](../tests/unit/passes/test_type_walk.py).
- Existing pipeline guides: [C parsing](../docs/parsing_c_to_cir_pipeline.md), [CIR passes](../docs/cir_passes_pipeline.md), [type mapping](../docs/analysis_type_mapping_pipeline.md), and [Mojo normalization](../docs/mojo_ir_normalization_pipeline.md).
- Reusable fixtures include `tests/surface/fixtures/{typedef_chain,callback_typedef_alias,opaque_forward_ptrs,fixed_array_field,scalar_fn_basic,enum_named_basic}`, the header corpus, stress fixtures and SQLite example.

Next build an isolated recursive Python/native type-mapping slice, then compare it
directly with production output and existing goldens before migrating production
Python code. Cover the former 107-input comparison's behaviors, especially nested
callbacks, typedef identity, all qualifiers/array shapes, shared children, fresh
output, named recursion, malformed inputs and cleanup. Keep Unicode normalization,
JSON omission/default rules, declaration names, ABI/layout decisions and CLI
behavior compatible. Separate CIR/MojoIR and pass-local state can be refactored
incrementally without flattening the type structure.

The full recursive mapper, declaration mapping, constant expressions, complete
frontend and serialization integration remain unimplemented. No performance
superiority or automatic `__enum` serde support was established.

# Faithful storage and safe C interoperability

## Agreed scope

Implement the same recursive model and behavior in the native generator and the
isolated Python reference. Keep the nightly generator and stable generated-code
compiler pins unchanged. IR JSON is an unversioned current-model debug format;
fixtures change with the schema. No migration decoder, type-node arena, mapping
memoization, compiler patch, automatic C bridge or extended-float evaluator.

## Implementation contracts

1. `TargetABI.float_abi` records Clang-probed format, size and alignment. The
   header-free probe honors frontend flags, including `-mlong-double-64`.
   `TargetQueries` owns source/target geometry and validated call-profile queries.
2. `representation` facts distinguish numeric values, faithful storage and
   unsupported geometry. `OpaqueStorageType(size_bytes, align_bytes)` has exact
   positive extent and power-of-two alignment; it never implies arithmetic or
   C call compatibility. Pure mapping produces fresh recursive outputs.
3. Record storage analysis checks actual target offsets, alignment and extent.
   Unsupported value fields trigger whole-record opaque storage. Verified opaque
   nominal children can be embedded in typed parents; by-value cycles cannot.
   Pointers retain usable storage types, with unknown pointees erased safely.
4. C ABI checks are distinct from storage checks. The validated profile is Linux
   x86-64, little endian, 8-byte pointers. Known scalar, pointer, complex float/
   double, float32x4 vector and eligible record transport retain existing paths.
   Unknown profiles, unsupported formats and unproven signatures become
   diagnostic, non-callable stubs; invalid callback signatures become opaque
   addresses. Direct fixed-array aggregate returns keep the existing `abi("C")`
   route. Dynamic loading still requires register-passable returns. No general
   machine ABI classifier is claimed.
5. Mapping applies standard C array-parameter adjustment using the source ABI's
   pointer geometry. Top-level CIR retains declared array shapes. Array lowering
   retains element qualifiers, including through typedefs. Pure type mapping of
   an array remains an array. Callback parameters use the same adjustment rule.
6. Unsupported extended floating literals/casts cannot silently narrow. `sizeof`
   evaluates source geometry independently of numeric representation. Storage-only
   globals and unsupported constants receive stubs. Integer alias names cannot
   override source signedness or geometry.
7. Normalization expands logical padding spans into width-specific physical
   members with unique names. The printer and layout generator consume the same
   final member list. Finalized validation rejects unresolved padding and invalid
   target expressions/types before emission.

## Files and test boundaries

Production contracts live under `mojo/mojo_bindgen/{ir,serde}.mojo`,
`analysis/facts/{target,representation,parameter_types,record_storage,c_abi}.mojo`,
`analysis/mojo/`, and `codegen/`; the optional reference mirrors these boundaries.
`tests/mojo/unit/test_representation.mojo` covers formats, storage, expression
rejection, physical padding, alias semantics and unsafe calls at O0/O3.

The shared `opaque_storage` C fixture checks size/alignment, array stride, real C
read/write and guard sentinels through pointers, nested opaque records and unions.
Its native runtime recipe also exercises compatible binary64 `long double` calls
under `-mlong-double-64` in both link modes and compiler optimization levels.
Existing complex and const-array fixtures perform actual calls. Complete runtime
layout fixtures include system `max_align_t` and require `large_alignment` to pass.

Frozen native debug vectors are refreshed from passing Python reference
assertions, never from native output. The optional maintenance plugin
`legacy/python/scripts/capture_native_reference.py` stages captures under the
ignored build directory; native acceptance imports neither it nor pytest.
Historical experiment evidence in `mojo_rewrite_results.md` remains unchanged.

## Validation record

Validated on Linux x86-64 with generator Mojo `1.3.0.dev2026103105`, generated
code Mojo `1.2.0`, and the same Clang 18 SDK for both implementations.

- The one-time Vulkan stress run uses Khronos Vulkan-Headers `v1.4.367`, revision
  `9fbc2a782ee3f8a4db64e7d991e23da75e893f44`. Default/beta headers in both link
  modes produce semantically equal CIR/MojoIR and byte-identical binding/layout
  source against the Python reference. All four binding modules precompile.
- Complete stable-O3 Vulkan layouts pass **1,439/1,439** (default/direct) and
  **1,458/1,458** (beta/dynamic), with no skips. These include system `max_align_t`;
  no declaration filter or expected layout failure remains. Both loader smoke
  programs query the installed Vulkan loader successfully. GPU rendering is not
  tested. Scratch reports live under ignored `mojo/build/vulkan-representation-safety/`.
- The 32 live example JSON/frontend parity cases pass with stable runtime checks.

- Full isolated Python reference suite: **527 passed**, including live native
  differential comparisons, both link modes, generated-binding/layout execution,
  and the four real examples. Its light gate passes **420 tests**, with Ruff and
  Pyright clean. Root facade/coordinator checks pass **13 + 17 tests**.
- Wheel and sdist build successfully. The final wheel passes all three pinned
  minimal-OS gates (installed runtime, system headers, C toolchain). The final
  Conda build passes installed CLI, direct executable and public Mojo API checks.
  These are local candidates, with no package or release publication.

- Full native acceptance: **28/28 TestSuite programs**, **516 passing test
  executions**, at O0/O3, with no failures or skips. The final run reuses 314 build
  artifacts and covers current-model vectors, frontend/CLI contracts, shared
  surface/corpus/stress, examples, stable runtime and complete layout sidecars.
  Native formatting passes. Frozen exact-file checks are refreshed from the
  Python captures alongside IR fields and retain their byte-for-byte assertions.

The historical `max_align_t` filter and expected `large_alignment` failure are
removed. Unknown-geometry declarations also produce safe comment stubs, allowing
unrelated valid declarations to finish generation. Compiler/runtime pins and the
historical experiment ledger are unchanged.

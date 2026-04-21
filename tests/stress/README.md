# Stress Fixtures

Stress is now a non-golden regression layer for intentionally pathological
headers.

- `fixtures/pathological_core/`
  Deep declaration-topology coverage: anonymous nesting, callback typedef
  layering, pointer-to-array declarators, function-pointer returns, recursive
  records, atomics, vectors, complex scalars, globals, and incomplete records.
- `fixtures/pathological_macros/`
  Supported and unsupported macro forms preserved in IR.
- `fixtures/pathological_layout/`
  Bitfields, zero-width barriers, packed/explicit-aligned layouts, and flexible
  or incomplete tail arrays.

Stress tests should assert:

- parsing succeeds
- `Unit -> JSON -> Unit` round-trips cleanly
- Mojo generation succeeds in both portable and strict-ABI modes
- a few structural invariants for especially fragile declarations

Stress does not snapshot emitted Mojo or annotated IR. Exact emitted text now
belongs in `tests/surface/`, including alignment-policy matrix cases.

# E2E Bindgen Tests

This directory contains end-to-end tests that validate C -> bindgen -> Mojo runtime behavior.

## Run

From the repo root:

```bash
pixi run pytest tests/e2e -v -s
```

The `tests/e2e` suite is also marked as `e2e`, `slow`, and `expensive`, so you
can select or exclude it from broader runs:

```bash
pixi run pytest -q -m e2e
pixi run pytest -q -m "not expensive"
```

Run only the new golden runtime suite:

```bash
pixi run pytest tests/e2e/test_golden_runtime.py -v -s
```

## Golden Runtime Corpus

`tests/e2e/golden` is a runtime-first golden corpus. Every case must include:

- `input.h`
- `impl.c`
- `runner_external.mojo`
- `runner_dl.mojo`
- `expect.emit.external.mojo`
- `expect.emit.owned_dl_handle.mojo`
- `expect.runtime.external.json`
- `expect.runtime.owned_dl_handle.json`
- `status.json`

`status.json` tracks expected outcomes per phase:

- `pass`
- `known_fail_bindgen`
- `known_fail_mojo`
- `known_fail_abi`
- `unsupported`
- `toolchain_variant`

The test runner reports:

- unexpected regressions (expected `pass`, observed fail)
- unexpected fixes (expected non-pass, observed pass)
- still-known-fail states as `xfail`

## Existing Coverage

- `test_runtime_ffi.py`: legacy fixture-based runtime checks.
- parser/emit surface checks now live under `tests/unit/` and `tests/stress/`.
- `test_golden_runtime.py`: comprehensive golden runtime suite with explicit failure attribution.

## Golden Case Matrix

Each golden case has a `status.json` with per-phase status. The summary below reports the effective case status today.

| Case | What it tests | Status | Reason if failing |
| --- | --- | --- | --- |
| `functional_math` | Basic scalar function bindings (`int32`, `double`, `uint64`) and runtime calls in external + owned-dl modes. | pass | n/a |
| `functional_records` | Struct/enum by-value/by-field behavior and runtime ABI compatibility. | pass | n/a |
| `full_surface_runtime` | Broad ABI surface: unions, bitfields, packed structs, callbacks, arrays, pointers, volatile/restrict, globals. | pass | n/a |
| `incomplete_array_padding` | Flexible/incomplete array member layout and emitted struct shape (`payload[]` style headers). | pass | n/a |
| `large_alignment` | Explicit alignment attributes (`aligned(16)`), offset/alignment ABI checks via runtime helpers. | pass | n/a |
| `opaque_forward` | Forward-declared opaque `union` + `struct` pointer signatures and callability. | pass | n/a |
| `const_array_decay` | `const T arr[N]` parameter decay semantics and wrapper emission/runtime behavior. | pass | n/a |
| `ptr_to_array` | Pointer-to-array declarations (`int (*p)[N]`) from upstream bindgen edge cases. | pass | n/a |
| `fnptr_return` | Function returning function-pointer (`fn -> fnptr`) lowering and wrapper generation. | pass | n/a |
| `anon_struct_union` | Anonymous struct-inside-union nesting and field resolution. | pass | n/a |
| `atomic_types_runtime` | Atomic counter increment/decrement functional checks; includes emitted atomic global note and verifies mode-specific runtime behavior. | pass | n/a |
| `globals_consts_runtime` | Mutable and `const` scalar globals via generated `GlobalVar` / `GlobalConst`; runtime uses `LD_PRELOAD` on the built `.so` so `dlsym` can resolve symbols (Mojo link does not always emit `DT_NEEDED` for `-l`). | pass | n/a |
| `complex_types_runtime` | Complex arithmetic through `_Complex float` bindings, asserting real/imag outputs in both linking modes. | pass | n/a |
| `vector_extension_types_runtime` | Vector-extension math (`vector_size(16)`) validated through scalar wrappers while preserving vector typedef emit coverage. | pass | n/a |

## Surface-Only Policy Coverage

- `test_bindgen_surface.py` now includes an anonymous enum constants check to ensure these are emitted as constants (not as a synthesized named enum).
- Anonymous struct/union members are expected to survive as synthetic carrier fields in emitted Mojo, rather than being flattened into promoted outer fields.

## Cleanup Notes

- Audited files under `tests/e2e` and did not remove anything automatically because all current files are referenced by active tests:
  - golden corpus files are required by `test_golden_runtime.py` schema checks,
  - fixture files are still used by `test_runtime_ffi.py`.

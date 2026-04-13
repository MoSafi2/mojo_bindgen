# E2E Bindgen Tests

This directory contains end-to-end tests that validate C -> bindgen -> Mojo runtime behavior.

## Run

From the repo root:

```bash
pixi run pytest tests/e2e -v -s
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
| `p0_incomplete_array_padding` | Flexible/incomplete array member layout and emitted struct shape (`payload[]` style headers). | pass | n/a |
| `p0_large_alignment` | Explicit alignment attributes (`aligned(16)`), offset/alignment ABI checks via runtime helpers. | pass | n/a |
| `p1_opaque_forward` | Forward-declared opaque `union` + `struct` pointer signatures and callability. | pass | n/a |
| `p1_const_array_decay` | `const T arr[N]` parameter decay semantics and wrapper emission/runtime behavior. | pass | n/a |
| `p0_ptr_to_array` | Pointer-to-array declarations (`int (*p)[N]`) from upstream bindgen edge cases. | known_fail_bindgen | Current bindgen path does not yet fully support pointer-to-array declarations for wrapper generation. |
| `p0_fnptr_return` | Function returning function-pointer (`fn -> fnptr`) lowering and wrapper generation. | known_fail_bindgen | Current bindgen path does not yet fully support function-pointer return type lowering. |
| `p1_anon_struct_union` | Anonymous struct-inside-union nesting and field resolution. | known_fail_bindgen | Current bindgen path does not yet fully support anonymous nested union/struct field lowering. |

## Surface-Only Policy Coverage

- `test_bindgen_surface.py` now includes an anonymous enum constants check to ensure these are emitted as constants (not as a synthesized named enum).

## Cleanup Notes

- Audited files under `tests/e2e` and did not remove anything automatically because all current files are referenced by active tests:
  - golden corpus files are required by `test_golden_runtime.py` schema checks,
  - fixture files are still used by `test_runtime_ffi.py`.

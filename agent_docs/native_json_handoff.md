# Python JSON handoff to the native backend

The current native library consumes both debug representations emitted by the
Python package. They are unversioned current-model IR, so update producers and
consumers together when the schema changes.

- Python `--dump-cir PATH`: raw `Unit`. Native `loads_cir` reconstructs its closed
  recursive CIR families, then `generate_from_unit` runs validation,
  canonicalization, analysis, mapping, policies, normalization, and both printers.
  Linking mode and the optional library path are separate generation options;
  raw CIR does not encode them.
- Python `--dump-mojo-ir PATH`: finalized `MojoModule`. Native `loads_mojo_ir` loads
  it and `render_mojo_module` prints bindings. It already contains linking options
  and target dependencies. A target dump alone has no source record geometry for
  regenerating layout tests.

Only the test harness invokes the Python frontend/reference. The native executable
reads the dump directly from disk and neither imports nor invokes Python.

## Reproduce the example stress test

From the repository root:

```bash
pixi run --locked native-example-parity
```

This delegates through `examples/pixi.toml` and its independent lock to provision
Cairo, libpng, SQLite and zlib headers/runtime libraries. The root stable compiler
and pinned native nightly retain their existing dependency locks. CI installs the
example environment before the native parity gate. A direct pytest invocation
skips these tests if that optional library environment has not been installed.

The lasting test is `tests/parity/test_native_examples.py`. It uses actual Python
CLI dump files, not handcrafted JSON or a shared runtime representation. The
standalone native driver is `tests/mojo/drivers/json_backend_driver.mojo`.

For each example, each linking mode, and both O0/O3 native builds, it:

1. Runs Python's CLI with both dump flags and keeps its binding/layout output.
2. Passes the raw CIR JSON file to the native executable; compares normalized CIR
   and finalized MojoIR semantically and binding/layout source byte-for-byte.
3. Passes finalized MojoIR JSON directly to the native printer; verifies its
   roundtrip and byte-identical binding source.
4. Verifies that the input JSON files remain unchanged.
5. Copies the existing example smoke program beside the newly generated bindings,
   compiles with the separate stable SDK, and runs against the locked libraries.

Copying the smoke program is necessary: compiling it in its original example
folder can import ignored stale generated bindings before searching `-I` paths.
Tests run in temporary directories and do not replace existing example outputs.
Layout source is compared in full; these large example sidecars are not executed.
The two known Python layout-test limitations remain documented in
[native_backend_plan.md](native_backend_plan.md#preserved-reference-limitations).

## Standalone file handoff

This is a test/debug driver, not the future native header CLI. For a raw CIR dump:

```bash
pixi run --locked mojo-bindgen /path/to/header.h --library demo --link-name demo \
  --dump-cir /tmp/demo.cir.json --dump-mojo-ir /tmp/demo.mojo_ir.json \
  --output /tmp/python_bindings.mojo
pixi run --manifest-path mojo/pixi.toml --locked mojo build -I mojo \
  tests/mojo/drivers/json_backend_driver.mojo -o mojo/build/json-backend
mkdir -p /tmp/native-bindings
LD_LIBRARY_PATH="$PWD/mojo/.pixi/envs/default/lib" mojo/build/json-backend \
  cir /tmp/demo.cir.json /tmp/native-bindings bindings external_call
```

Replace the final linking argument with `owned_dl_handle` and append a shared
library path to select dynamic loading. For a finalized target dump:

```bash
LD_LIBRARY_PATH="$PWD/mojo/.pixi/envs/default/lib" mojo/build/json-backend \
  mojo-ir /tmp/demo.mojo_ir.json /tmp/native-bindings bindings
```

The CIR path writes bindings, layout-test source, normalized CIR JSON, and target
JSON. The MojoIR path writes bindings and target JSON. The explicit runtime path
prevents an activated stable environment from supplying its runtime to a nightly
executable.

## Measured example results (2026-11-01, Linux x86-64)

`pixi run --locked native-example-parity`: **16 passed**. All **32 JSON-stage
handoffs** and **16 stable compilation/runtime smoke runs** passed. Both linking
modes reproduced Python's sources exactly at both optimization levels, with no
production-backend changes required by these examples.

Counts for one linking mode, using the locked example headers on this host:

| Example | Raw CIR declarations | Final MojoIR declarations | Raw CIR JSON bytes | Final MojoIR JSON bytes |
| --- | ---: | ---: | ---: | ---: |
| zlib | 1,576 | 1,212 | 1,466,949 | 1,074,411 |
| Cairo | 561 | 750 | 1,703,028 | 1,249,236 |
| libpng | 1,410 | 1,349 | 2,507,328 | 1,510,422 |
| SQLite | 904 | 1,076 | 2,092,166 | 1,547,053 |

Header/system include contents can change these counts on another host. The
asserted gates compare the actual current dumps and emitted sources; they do not
pin host-specific declaration counts or impose a performance target.

Final integration gates after adding the example handoff coverage:

- `pixi run --locked test`: **472 passed**.
- `pixi run --locked check-light`: Ruff formatting/lint, Pyright, and **396 passed;
  76 deselected**.
- Native formatting check passed. The native production backend was unchanged
  by the example stress test; its O0/O3 ownership and installed-package validation
  are recorded in the backend ledger.

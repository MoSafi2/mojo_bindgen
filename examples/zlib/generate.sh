#!/usr/bin/env bash
# Generate and run the zlib owned-dl-handle example.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/common.sh"
example_init "${BASH_SOURCE[0]}"

HEADER="$(pkg_header zlib zlib.h)" || die "zlib.h not found; install zlib development headers."
DYLIB="$(find_dylib z zlib)" || die "libz shared library not found."

generate_owned_bindings "$HEADER" z z "$DYLIB" zlib_bindings.mojo
build_smoke zlib_dl_smoke.mojo zlib_dl_smoke

echo "Wrote $HERE/zlib_bindings.mojo (dlopen: $DYLIB)"
"$HERE/zlib_dl_smoke"

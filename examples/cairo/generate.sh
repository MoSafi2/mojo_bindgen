#!/usr/bin/env bash
# Generate and run the Cairo owned-dl-handle example.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/common.sh"
example_init "${BASH_SOURCE[0]}"

HEADER="$(pkg_header cairo cairo/cairo.h)" || die "cairo/cairo.h not found; install Cairo development headers."
DYLIB="$(find_dylib cairo cairo)" || die "libcairo shared library not found."

generate_owned_bindings "$HEADER" cairo cairo "$DYLIB" cairo_bindings.mojo
build_smoke cairo_smoke.mojo cairo_smoke

echo "Wrote $HERE/cairo_bindings.mojo (dlopen: $DYLIB)"
"$HERE/cairo_smoke"

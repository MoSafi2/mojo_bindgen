#!/usr/bin/env bash
# Generate and run the libpng owned-dl-handle example.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/common.sh"
example_init "${BASH_SOURCE[0]}"

PKG="libpng"
if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists libpng16; then
  PKG="libpng16"
fi

HEADER="$(pkg_header "$PKG" png.h /usr/include/libpng16/png.h)" ||
  die "png.h not found; install libpng development headers."
LINK_NAME="$(pkg_link_name "$PKG" png16)"
DYLIB="$(find_dylib "$LINK_NAME" "$PKG")" || die "lib$LINK_NAME shared library not found."

generate_owned_bindings "$HEADER" "$LINK_NAME" "$LINK_NAME" "$DYLIB" libpng_bindings.mojo
build_smoke libpng_smoke.mojo libpng_smoke

echo "Wrote $HERE/libpng_bindings.mojo (dlopen: $DYLIB)"
"$HERE/libpng_smoke"

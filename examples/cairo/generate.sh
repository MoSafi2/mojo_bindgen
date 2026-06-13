#!/usr/bin/env bash
# Example driver for the system Cairo header.
# It finds the real primary `cairo.h`, generates `cairo_bindings.mojo`, and
# builds/runs `cairo_smoke.mojo` to prove the emitted bindings link and work.
#
# Expects:
#   - mojo-bindgen on PATH (e.g. `pixi shell` from the repository root), or Pixi
#     at the repo root so this script can run `pixi run mojo-bindgen`.
#   - Development headers for Cairo (e.g. libcairo2-dev on Debian/Ubuntu).
#
# Notes:
#   - mojo-bindgen emits declarations from the primary header only, so this
#     script locates `cairo/cairo.h` directly instead of using a wrapper.
#   - The shared-library link name is `cairo`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

source "$REPO_ROOT/examples/common.sh"
set_mojo_bindgen_cmd BG "$REPO_ROOT"
set_mojo_cmd MOJO "$REPO_ROOT"

find_cairo_h() {
  local d
  if command -v pkg-config >/dev/null 2>&1; then
    while read -r -a flags; do
      for flag in "${flags[@]}"; do
        if [[ "$flag" == -I* ]]; then
          d="${flag#-I}"
          if [[ -f "$d/cairo/cairo.h" ]]; then
            echo "$d/cairo/cairo.h"
            return 0
          fi
          if [[ "$d" == */cairo && -f "$d/cairo.h" ]]; then
            echo "$d/cairo.h"
            return 0
          fi
        fi
      done
    done < <(pkg-config --cflags-only-I cairo 2>/dev/null || true)
  fi
  for d in /usr/include /usr/local/include /opt/homebrew/include; do
    if [[ -f "$d/cairo/cairo.h" ]]; then
      echo "$d/cairo/cairo.h"
      return 0
    fi
  done
  return 1
}

CAIRO_H="$(find_cairo_h)" || {
  echo "mojo-bindgen cairo example: could not find cairo/cairo.h (install Cairo development headers)." >&2
  exit 1
}

generate_bindings "$CAIRO_H" cairo cairo cairo_bindings.mojo

OBJ="$(mktemp "${TMPDIR:-/tmp}/cairo-bindings-XXXXXX.o")"
trap 'rm -f "$OBJ"' EXIT
build_bindings_object cairo_bindings.mojo "$OBJ"
"${MOJO[@]}" build cairo_smoke.mojo -I "$HERE" -Xlinker -lcairo -o cairo_smoke

echo "Wrote $HERE/cairo_bindings.mojo and cairo_bindings_layout_tests.mojo (from $CAIRO_H)"
echo "Running cairo_smoke (runtime render + file round-trip proof)"
"$HERE/cairo_smoke"

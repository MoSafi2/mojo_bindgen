#!/usr/bin/env bash
# Example driver for the system libpng header.
# It finds the real primary `png.h`, generates `libpng_bindings.mojo`, and
# builds/runs `libpng_smoke.mojo` to verify the bindings link and execute.
#
# Expects:
#   - mojo-bindgen on PATH (e.g. `pixi shell` from the repository root), or Pixi
#     at the repo root so this script can run `pixi run mojo-bindgen`.
#   - Development headers for libpng (e.g. libpng-dev on Debian/Ubuntu).
#
# Notes:
#   - mojo-bindgen emits declarations from the primary header only, so this
#     script locates `png.h` directly instead of using a wrapper header.
#   - The link name may be `png16` or a similar system-specific variant; this
#     script derives it from `pkg-config` when possible.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

source "$REPO_ROOT/examples/common.sh"
set_mojo_bindgen_cmd BG "$REPO_ROOT"
set_mojo_cmd MOJO "$REPO_ROOT"

detect_png_pkg() {
  local module
  for module in libpng libpng16; do
    if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists "$module" 2>/dev/null; then
      echo "$module"
      return 0
    fi
  done
  return 1
}

find_png_h() {
  local module="$1"
  local d
  if command -v pkg-config >/dev/null 2>&1; then
    while read -r -a flags; do
      for flag in "${flags[@]}"; do
        if [[ "$flag" == -I* ]]; then
          d="${flag#-I}"
          if [[ -f "$d/png.h" ]]; then
            echo "$d/png.h"
            return 0
          fi
          if [[ -f "$d/libpng16/png.h" ]]; then
            echo "$d/libpng16/png.h"
            return 0
          fi
        fi
      done
    done < <(pkg-config --cflags-only-I "$module" 2>/dev/null || true)
  fi
  for d in /usr/include /usr/local/include /opt/homebrew/include; do
    if [[ -f "$d/png.h" ]]; then
      echo "$d/png.h"
      return 0
    fi
    if [[ -f "$d/libpng16/png.h" ]]; then
      echo "$d/libpng16/png.h"
      return 0
    fi
  done
  return 1
}

find_link_name() {
  local module="$1"
  local token
  if command -v pkg-config >/dev/null 2>&1; then
    while read -r -a flags; do
      for token in "${flags[@]}"; do
        if [[ "$token" == -lpng* ]]; then
          echo "${token#-l}"
          return 0
        fi
      done
    done < <(pkg-config --libs "$module" 2>/dev/null || true)
  fi
  echo "png16"
}

PNG_PKG="$(detect_png_pkg || true)"
if [[ -z "${PNG_PKG:-}" ]]; then
  PNG_PKG="libpng"
fi

PNG_H="$(find_png_h "$PNG_PKG")" || {
  echo "mojo-bindgen libpng example: could not find png.h (install libpng development headers)." >&2
  exit 1
}
LINK_NAME="$(find_link_name "$PNG_PKG")"

generate_bindings "$PNG_H" "$LINK_NAME" "$LINK_NAME" libpng_bindings.mojo

OBJ="$(mktemp "${TMPDIR:-/tmp}/libpng-bindings-XXXXXX.o")"
trap 'rm -f "$OBJ"' EXIT
build_bindings_object libpng_bindings.mojo "$OBJ" -Xlinker "-l$LINK_NAME"
"${MOJO[@]}" build libpng_smoke.mojo -I "$HERE" -Xlinker "-l$LINK_NAME" -o libpng_smoke

echo "Wrote $HERE/libpng_bindings.mojo and libpng_bindings_layout_tests.mojo (from $PNG_H)"
echo "Running libpng_smoke (runtime version probe proof)"
"$HERE/libpng_smoke"

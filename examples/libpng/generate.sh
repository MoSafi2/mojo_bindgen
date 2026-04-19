#!/usr/bin/env bash
# Generate Mojo FFI bindings for the system libpng (libpng*.so / libpng*.dylib / libpng*.dll).
#
# Prerequisites:
#   - mojo-bindgen on PATH (e.g. `pixi shell` from the repository root), or Pixi
#     at the repo root so this script can run `pixi run mojo-bindgen`.
#   - Development headers for libpng (e.g. libpng-dev on Debian/Ubuntu).
#
# mojo-bindgen only emits declarations from the *primary* header file. A thin
# wrapper that only #include's <png.h> produces an empty module because every
# declaration is attributed to png.h, not the wrapper — so we locate png.h
# and pass it as the input file.
#
# Also builds/runs libpng_smoke.mojo to prove generated bindings work at runtime.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

if command -v mojo-bindgen >/dev/null 2>&1; then
  BG=(mojo-bindgen)
else
  BG=(pixi run --manifest-path "$REPO_ROOT/pixi.toml" mojo-bindgen)
fi

if command -v mojo >/dev/null 2>&1; then
  MOJO=(mojo)
else
  MOJO=(pixi run --manifest-path "$REPO_ROOT/pixi.toml" mojo)
fi

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

"${BG[@]}" "$PNG_H" --library "$LINK_NAME" --link-name "$LINK_NAME" -o libpng_bindings.mojo

OBJ="$(mktemp "${TMPDIR:-/tmp}/libpng-bindings-XXXXXX.o")"
trap 'rm -f "$OBJ"' EXIT
"${MOJO[@]}" build libpng_bindings.mojo -Xlinker "-l$LINK_NAME" --emit object -o "$OBJ"
"${MOJO[@]}" build libpng_smoke.mojo -I "$HERE" -Xlinker "-l$LINK_NAME" -o libpng_smoke

echo "Wrote $HERE/libpng_bindings.mojo (from $PNG_H)"
echo "Running libpng_smoke (runtime version probe proof)"
"$HERE/libpng_smoke"

#!/usr/bin/env bash
# Generate Mojo FFI bindings for the system Cairo (libcairo.so / libcairo.dylib / cairo.dll).
#
# Prerequisites:
#   - mojo-bindgen on PATH (e.g. `pixi shell` from the repository root), or Pixi
#     at the repo root so this script can run `pixi run mojo-bindgen`.
#   - Development headers for Cairo (e.g. libcairo2-dev on Debian/Ubuntu).
#
# mojo-bindgen only emits declarations from the *primary* header file. A thin
# wrapper that only #include's <cairo/cairo.h> produces an empty module because
# every declaration is attributed to cairo/cairo.h, not the wrapper — so we
# locate cairo/cairo.h and pass it as the input file.
#
# The shared library link name is "cairo" (libcairo.so).
# Also builds/runs cairo_smoke.mojo to prove generated bindings work at runtime.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

if command -v mojo-bindgen >/dev/null 2>&1; then
  BG=(mojo-bindgen)
else
  BG=(pixi run --manifest-path "$REPO_ROOT/pixi.toml" mojo-bindgen)
fi

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

"${BG[@]}" "$CAIRO_H" --library cairo --link-name cairo -o cairo_bindings.mojo

if command -v mojo >/dev/null 2>&1; then
  MJ=(mojo)
else
  MJ=(pixi run --manifest-path "$REPO_ROOT/pixi.toml" mojo)
fi
OBJ="$(mktemp "${TMPDIR:-/tmp}/cairo-bindings-XXXXXX.o")"
trap 'rm -f "$OBJ"' EXIT
"${MJ[@]}" build --emit object cairo_bindings.mojo -o "$OBJ"
"${MJ[@]}" build cairo_smoke_2.mojo -I "$HERE" -Xlinker -lcairo -o cairo_smoke_2

echo "Wrote $HERE/cairo_bindings.mojo (from $CAIRO_H)"
echo "Running cairo_smoke (runtime render + file round-trip proof)"
"$HERE/cairo_smoke_2"

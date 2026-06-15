#!/usr/bin/env bash
# Example driver for the system zlib header.
# It generates three variants:
#   - `zlib_bindings.mojo` for `external_call`
#   - `zlib_bindings_dylib_lazy.mojo` for `dylib-lazy`
#   - `zlib_bindings_dylib_checked.mojo` for `dylib-checked`
# and then builds/runs smoke tests for the dynamic-loaded paths.
#
# Expects:
#   - mojo-bindgen on PATH (e.g. `pixi shell` from the repository root), or Pixi
#     at the repo root so this script can run `pixi run mojo-bindgen`.
#   - Development headers for zlib (e.g. zlib1g-dev on Debian/Ubuntu).
#
# Notes:
#   - mojo-bindgen emits declarations from the primary header only, so this
#     script locates `zlib.h` directly instead of using a wrapper.
#   - The short link name is `z`, not `zlib`.
#   - The dynamic variants are skipped if no shared-library path can be found.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

source "$REPO_ROOT/examples/common.sh"
set_mojo_bindgen_cmd BG "$REPO_ROOT"
set_mojo_cmd MOJO "$REPO_ROOT"

find_zlib_h() {
  local d
  if command -v pkg-config >/dev/null 2>&1; then
    while read -r -a flags; do
      for flag in "${flags[@]}"; do
        if [[ "$flag" == -I* ]]; then
          d="${flag#-I}"
          if [[ -f "$d/zlib.h" ]]; then
            echo "$d/zlib.h"
            return 0
          fi
        fi
      done
    done < <(pkg-config --cflags-only-I zlib 2>/dev/null || true)
  fi
  for d in /usr/include /usr/local/include /opt/homebrew/include; do
    if [[ -f "$d/zlib.h" ]]; then
      echo "$d/zlib.h"
      return 0
    fi
  done
  return 1
}

# Path to the zlib shared library used as `--library-path`.
find_libz_so() {
  local p
  if command -v gcc >/dev/null 2>&1; then
    for name in libz.so libz.dylib; do
      p="$(gcc -print-file-name="$name" 2>/dev/null || true)"
      if [[ -n "$p" ]]; then
        if command -v realpath >/dev/null 2>&1; then
          p="$(realpath "$p" 2>/dev/null || echo "$p")"
        fi
        if [[ -f "$p" ]]; then
          echo "$p"
          return 0
        fi
      fi
    done
  fi
  for p in \
    /lib/x86_64-linux-gnu/libz.so.1 \
    /usr/lib/x86_64-linux-gnu/libz.so.1 \
    /usr/lib/libz.so \
    /lib/libz.so.1 \
    /opt/homebrew/lib/libz.dylib \
    /usr/lib/libz.dylib
  do
    if [[ -f "$p" ]]; then
      if command -v realpath >/dev/null 2>&1; then
        realpath "$p"
      else
        echo "$p"
      fi
      return 0
    fi
  done
  return 1
}

ZLIB_H="$(find_zlib_h)" || {
  echo "mojo-bindgen zlib example: could not find zlib.h (install zlib development headers)." >&2
  exit 1
}


generate_bindings "$ZLIB_H" z z zlib_bindings.mojo --link-mode external-call
build_bindings_object zlib_bindings.mojo zlib_bindings.o -Xlinker -lz

echo "Wrote $HERE/zlib_bindings.mojo, zlib_bindings_layout_tests.mojo, and zlib_bindings.o (from $ZLIB_H)"

LIBZ_SO="$(find_libz_so)" || true
if [[ -n "${LIBZ_SO:-}" ]]; then
  generate_bindings "$ZLIB_H" z z zlib_bindings_dylib_lazy.mojo \
    --link-mode dylib-lazy --library-path "$LIBZ_SO"
  generate_bindings "$ZLIB_H" z z zlib_bindings_dylib_checked.mojo \
    --link-mode dylib-checked --library-path "$LIBZ_SO"

  "${MOJO[@]}" build zlib_dylib_lazy_smoke.mojo -I "$HERE" -o zlib_dylib_lazy_smoke
  "${MOJO[@]}" build zlib_dylib_checked_smoke.mojo -I "$HERE" -o zlib_dylib_checked_smoke

  echo "Wrote $HERE/zlib_bindings_dylib_lazy.mojo and $HERE/zlib_bindings_dylib_checked.mojo (dlopen: $LIBZ_SO)"
  echo "Running zlib_dylib_lazy_smoke (dylib-lazy runtime proof)"
  "$HERE/zlib_dylib_lazy_smoke"
  echo "Running zlib_dylib_checked_smoke (dylib-checked runtime proof)"
  "$HERE/zlib_dylib_checked_smoke"
else
  echo "mojo-bindgen zlib example: could not locate libz shared library; skipping dynamic output." >&2
  echo "  (Install zlib and ensure gcc -print-file-name=libz.so resolves.)" >&2
fi

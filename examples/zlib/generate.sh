#!/usr/bin/env bash
# Generate Mojo FFI bindings for the system zlib (libz.so / libz.dylib / zlib.dll).
#
# Prerequisites:
#   - mojo-bindgen on PATH (e.g. `pixi shell` from the repository root), or Pixi
#     at the repo root so this script can run `pixi run mojo-bindgen`.
#   - Development headers for zlib (e.g. zlib1g-dev on Debian/Ubuntu).
#
# mojo-bindgen only emits declarations from the *primary* header file. A thin
# wrapper that only #include's <zlib.h> produces an empty module because every
# declaration is attributed to zlib.h, not the wrapper — so we locate zlib.h
# and pass it as the input file.
#
# The shared library short name is "z" (libz.so), not "zlib", so we pass
# --library z --link-name z.
#
# Two outputs:
#   - zlib_bindings.mojo — external_call (link-time); mojo build needs -lz.
#   - zlib_bindings_dl.mojo — OwnedDLHandle + --library-path-hint to libz;
#     zlib_dl_smoke.mojo builds a tiny binary that loads libz at runtime (no -lz).
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

# Path to the zlib shared library for OwnedDLHandle (--library-path-hint).
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

"${BG[@]}" "$ZLIB_H" --library z --link-name z -o zlib_bindings.mojo
"${MOJO[@]}" build zlib_bindings.mojo -Xlinker -lz --emit object -o zlib_bindings.o

echo "Wrote $HERE/zlib_bindings.mojo and zlib_bindings.o (from $ZLIB_H)"

LIBZ_SO="$(find_libz_so)" || true
if [[ -n "${LIBZ_SO:-}" ]]; then
  "${BG[@]}" "$ZLIB_H" --library z --link-name z \
    --linking owned_dl_handle --library-path-hint "$LIBZ_SO" -o zlib_bindings_dl.mojo
  "${MOJO[@]}" build zlib_dl_smoke.mojo -I "$HERE" -o zlib_dl_smoke
  echo "Wrote $HERE/zlib_bindings_dl.mojo (dlopen: $LIBZ_SO) and built zlib_dl_smoke"
else
  echo "mojo-bindgen zlib example: could not locate libz shared library; skipping OwnedDLHandle output." >&2
  echo "  (Install zlib and ensure gcc -print-file-name=libz.so resolves.)" >&2
fi

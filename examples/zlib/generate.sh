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
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

if command -v mojo-bindgen >/dev/null 2>&1; then
  BG=(mojo-bindgen)
else
  BG=(pixi run --manifest-path "$REPO_ROOT/pixi.toml" mojo-bindgen)
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

ZLIB_H="$(find_zlib_h)" || {
  echo "mojo-bindgen zlib example: could not find zlib.h (install zlib development headers)." >&2
  exit 1
}

"${BG[@]}" "$ZLIB_H" --library z --link-name z -o zlib_bindings.mojo && mojo build zlib_bindings.mojo

echo "Wrote $HERE/zlib_bindings.mojo (from $ZLIB_H)"

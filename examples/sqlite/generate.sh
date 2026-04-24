#!/usr/bin/env bash
# Example driver for SQLite.
# It uses the vendored `sqlite3.h` when present, otherwise a system header,
# generates `sqlite3_bindings.mojo`, and builds/runs `sqlite_smoke.mojo`.
#
# Expects:
#   - mojo-bindgen on PATH (e.g. `pixi shell` from the repository root), or Pixi
#     at the repo root so this script can run `pixi run mojo-bindgen`.
#   - Development headers for SQLite (e.g. libsqlite3-dev on Debian/Ubuntu), or use
#     the vendored examples/sqlite/sqlite3.h in this repository.
#
# Notes:
#   - mojo-bindgen emits declarations from the primary header only, so this
#     script passes `sqlite3.h` directly.
#   - `sqlite_smoke.mojo` links against `-lsqlite3`; the script also adds an
#     extra `-L...` when SQLite lives in a non-default environment path.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"

if command -v mojo-bindgen >/dev/null 2>&1; then
  BG=(mojo-bindgen)
else
  BG=(pixi run --manifest-path "$REPO_ROOT/pixi.toml" mojo-bindgen)
fi

# Use the repository Pixi environment so Mojo resolves `std` consistently.
MOJO=(pixi run --manifest-path "$REPO_ROOT/pixi.toml" mojo)

find_sqlite3_h() {
  if [[ -f "$HERE/sqlite3.h" ]]; then
    echo "$HERE/sqlite3.h"
    return 0
  fi
  local d
  if command -v pkg-config >/dev/null 2>&1; then
    while read -r -a flags; do
      for flag in "${flags[@]}"; do
        if [[ "$flag" == -I* ]]; then
          d="${flag#-I}"
          if [[ -f "$d/sqlite3.h" ]]; then
            echo "$d/sqlite3.h"
            return 0
          fi
        fi
      done
    done < <(pkg-config --cflags-only-I sqlite3 2>/dev/null || true)
  fi
  for d in /usr/include /usr/local/include /opt/homebrew/include; do
    if [[ -f "$d/sqlite3.h" ]]; then
      echo "$d/sqlite3.h"
      return 0
    fi
  done
  return 1
}

# Extra linker search path when SQLite is installed outside the default system path.
sqlite_link_extra() {
  local p
  if command -v pkg-config >/dev/null 2>&1; then
    while read -r -a flags; do
      for p in "${flags[@]}"; do
        if [[ "$p" == -L* ]]; then
          echo "$p"
          return 0
        fi
      done
    done < <(pkg-config --libs-only-L sqlite3 2>/dev/null || true)
  fi
  for p in "${CONDA_PREFIX:-}" "${PIXI_ENVIRONMENT:-}"; do
    if [[ -n "$p" && ( -f "$p/lib/libsqlite3.so" || -f "$p/lib/libsqlite3.dylib" ) ]]; then
      echo "-L$p/lib"
      return 0
    fi
  done
  if [[ -f "$REPO_ROOT/.pixi/envs/default/lib/libsqlite3.so" || -f "$REPO_ROOT/.pixi/envs/default/lib/libsqlite3.dylib" ]]; then
    echo "-L$REPO_ROOT/.pixi/envs/default/lib"
    return 0
  fi
  return 0
}

SQLITE_H="$(find_sqlite3_h)" || {
  echo "mojo-bindgen sqlite example: could not find sqlite3.h (install SQLite development headers or keep vendored sqlite3.h in examples/sqlite)." >&2
  exit 1
}

"${BG[@]}" "$SQLITE_H" --library sqlite3 --link-name sqlite3 -o sqlite3_bindings.mojo

LINK_EXTRA="$(sqlite_link_extra || true)"
OBJ="$(mktemp "${TMPDIR:-/tmp}/sqlite-bindings-XXXXXX.o")"
trap 'rm -f "$OBJ"' EXIT
"${MOJO[@]}" build sqlite3_bindings.mojo --emit object -o "$OBJ"
if [[ -n "$LINK_EXTRA" ]]; then
  # shellcheck disable=SC2206
  EXTRA=(-Xlinker "$LINK_EXTRA")
else
  EXTRA=()
fi
"${MOJO[@]}" build sqlite_smoke.mojo -I "$HERE" "${EXTRA[@]}" -Xlinker -lsqlite3 -o sqlite_smoke

echo "Wrote $HERE/sqlite3_bindings.mojo (from $SQLITE_H)"
echo "Running sqlite_smoke (composite runtime proof)"
"$HERE/sqlite_smoke"

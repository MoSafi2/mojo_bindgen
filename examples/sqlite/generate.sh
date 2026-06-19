#!/usr/bin/env bash
# Generate and run the SQLite owned-dl-handle example.
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/common.sh"
example_init "${BASH_SOURCE[0]}"

HEADER="$(pkg_header sqlite3 sqlite3.h "$HERE/sqlite3.h")" ||
  die "sqlite3.h not found; install SQLite development headers or keep examples/sqlite/sqlite3.h."
DYLIB="$(find_dylib sqlite3 sqlite3)" || die "libsqlite3 shared library not found."

generate_owned_bindings "$HEADER" sqlite3 sqlite3 "$DYLIB" sqlite3_bindings.mojo
build_smoke sqlite_smoke.mojo sqlite_smoke

echo "Wrote $HERE/sqlite3_bindings.mojo (dlopen: $DYLIB)"
"$HERE/sqlite_smoke"

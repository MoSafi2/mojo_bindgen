#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
native_root="${repo_root}/mojo"
mkdir -p "${native_root}/build"
mojo precompile "${native_root}/mojo_bindgen" -o "${native_root}/build/mojo_bindgen.mojoc"
mojo build -I "${native_root}" "${native_root}/main.mojo" -o "${native_root}/build/mojo-bindgen-mojo"

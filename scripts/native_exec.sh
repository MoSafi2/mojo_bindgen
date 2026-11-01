#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk="${MOJO_BINDGEN_SDK:-${repo_root}/mojo/.pixi/envs/default}"
export LD_LIBRARY_PATH="${sdk}/lib"
export MOJO_BINDGEN_CLANG_LIBRARY_PATH="${MOJO_BINDGEN_CLANG_LIBRARY_PATH:-${sdk}/lib/libclang.so}"
exec "${repo_root}/mojo/build/payload/bin/mojo-bindgen" "$@"

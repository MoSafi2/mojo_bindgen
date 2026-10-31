#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
shopt -s globstar nullglob
# One file per invocation avoids the formatter's multiprocessing dependency.
for source in "${repo_root}"/mojo/mojo_bindgen/**/*.mojo \
    "${repo_root}"/mojo/main.mojo "${repo_root}"/tests/mojo/**/*.mojo \
    "${repo_root}"/mojo/conda.recipe/*.mojo; do
    mblack --quiet --line-length 100 "$@" "${source}"
done

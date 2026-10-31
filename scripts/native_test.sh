#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${repo_root}/mojo/build/tests"
export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
shopt -s globstar nullglob
for optimization in 0 3; do
    for source in "${repo_root}"/tests/mojo/unit/**/test_*.mojo; do
        relative="${source#"${repo_root}/tests/mojo/unit/"}"
        binary="${repo_root}/mojo/build/tests/${relative//\//_}-O${optimization}"
        mojo build -I "${repo_root}/mojo" "-O${optimization}" --Werror "${source}" -o "${binary}"
        "${binary}"
    done
done

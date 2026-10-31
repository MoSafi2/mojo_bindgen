#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${repo_root}/mojo/build/tests"
export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
for optimization in 0 3; do
    binary="${repo_root}/mojo/build/tests/types-O${optimization}"
    mojo build -I "${repo_root}/mojo" "-O${optimization}" --Werror \
        "${repo_root}/tests/mojo/test_types.mojo" -o "${binary}"
    "${binary}"
done

#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${repo_root}/mojo/build/tmp"
export TMPDIR="${repo_root}/mojo/build/tmp"
upstream_channel="$(python "${repo_root}/scripts/native_package_channel.py")"
recipe="${repo_root}/mojo/conda.recipe/recipe.yaml"
if [[ -n "${MOJO_BINDGEN_SOURCE_REVISION:-}" ]]; then
    recipe="$(python "${repo_root}/scripts/render_conda_recipe.py" "$MOJO_BINDGEN_SOURCE_REVISION" "${repo_root}/mojo/build/release-recipe")"
fi
rattler-build build --recipe "${recipe}" \
    --output-dir "${repo_root}/mojo/build/conda" \
    -c "${upstream_channel}" -c https://conda.modular.com/max-nightly/ -c conda-forge "$@"

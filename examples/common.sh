#!/usr/bin/env bash
# Shared helpers for repository example generation scripts.

set -euo pipefail

example_repo_root() {
  local here="$1"
  cd "$here/../.." && pwd
}

set_mojo_bindgen_cmd() {
  local -n out="$1"
  local repo_root="$2"
  if command -v mojo-bindgen >/dev/null 2>&1; then
    out=(mojo-bindgen)
    return 0
  fi
  out=(pixi run --manifest-path "$repo_root/pixi.toml" mojo-bindgen)
}

set_mojo_cmd() {
  local -n out="$1"
  local repo_root="$2"
  if command -v mojo >/dev/null 2>&1; then
    out=(mojo)
    return 0
  fi
  out=(pixi run --manifest-path "$repo_root/pixi.toml" mojo)
}

set_repo_mojo_cmd() {
  local -n out="$1"
  local repo_root="$2"
  out=(pixi run --manifest-path "$repo_root/pixi.toml" mojo)
}

generate_bindings() {
  local header="$1"
  local library="$2"
  local link_name="$3"
  local output="$4"
  shift 4

  "${BG[@]}" "$header" \
    --library "$library" \
    --link-name "$link_name" \
    --layout-tests \
    --layout-test-output "${output%.mojo}_layout_tests.mojo" \
    "$@" \
    -o "$output"
}

build_bindings_object() {
  local source="$1"
  local object="$2"
  shift 2
  "${MOJO[@]}" build "$source" --emit object -o "$object" "$@"
}

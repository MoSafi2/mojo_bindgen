#!/usr/bin/env bash
# Shared helpers for example generation scripts.

set -euo pipefail

example_init() {
  HERE="$(cd "$(dirname "$1")" && pwd)"
  REPO_ROOT="$(cd "$HERE/../.." && pwd)"
  BG=(pixi run --manifest-path "$REPO_ROOT/pixi.toml" mojo-bindgen)
  MOJO=(pixi run --manifest-path "$REPO_ROOT/pixi.toml" mojo)
  cd "$HERE"
}

die() {
  echo "$*" >&2
  exit 1
}

first_existing() {
  local path
  for path in "$@"; do
    if [[ -f "$path" ]]; then
      if command -v realpath >/dev/null 2>&1; then
        realpath "$path"
      else
        echo "$path"
      fi
      return 0
    fi
  done
  return 1
}

pkg_header() {
  local pkg="$1"
  local relative="$2"
  shift 2

  local flag dir
  if command -v pkg-config >/dev/null 2>&1; then
    while read -r -a flags; do
      for flag in "${flags[@]}"; do
        if [[ "$flag" == -I* ]]; then
          dir="${flag#-I}"
          first_existing "$dir/$relative" "$dir/$(basename "$relative")" && return 0
        fi
      done
    done < <(pkg-config --cflags-only-I "$pkg" 2>/dev/null || true)
  fi

  first_existing "$@" \
    "/usr/include/$relative" \
    "/usr/local/include/$relative" \
    "/opt/homebrew/include/$relative"
}

pkg_link_name() {
  local pkg="$1"
  local fallback="$2"
  local flag
  if command -v pkg-config >/dev/null 2>&1; then
    while read -r -a flags; do
      for flag in "${flags[@]}"; do
        if [[ "$flag" == -l* ]]; then
          echo "${flag#-l}"
          return 0
        fi
      done
    done < <(pkg-config --libs "$pkg" 2>/dev/null || true)
  fi
  echo "$fallback"
}

find_dylib() {
  local link_name="$1"
  local pkg="${2:-}"
  local name path flag dir
  local names=("lib${link_name}.so" "lib${link_name}.so.1" "lib${link_name}.dylib")

  if [[ -n "$pkg" ]] && command -v pkg-config >/dev/null 2>&1; then
    while read -r -a flags; do
      for flag in "${flags[@]}"; do
        if [[ "$flag" == -L* ]]; then
          dir="${flag#-L}"
          for name in "${names[@]}"; do
            first_existing "$dir/$name" && return 0
          done
        fi
      done
    done < <(pkg-config --libs-only-L "$pkg" 2>/dev/null || true)
  fi

  if command -v gcc >/dev/null 2>&1; then
    for name in "${names[@]}"; do
      path="$(gcc -print-file-name="$name" 2>/dev/null || true)"
      first_existing "$path" && return 0
    done
  fi

  first_existing \
    "$REPO_ROOT/.pixi/envs/default/lib/lib${link_name}.so" \
    "$REPO_ROOT/.pixi/envs/default/lib/lib${link_name}.dylib" \
    "/lib/x86_64-linux-gnu/lib${link_name}.so" \
    "/lib/x86_64-linux-gnu/lib${link_name}.so.1" \
    "/usr/lib/x86_64-linux-gnu/lib${link_name}.so" \
    "/usr/lib/x86_64-linux-gnu/lib${link_name}.so.1" \
    "/usr/lib/lib${link_name}.so" \
    "/usr/lib/lib${link_name}.so.1" \
    "/opt/homebrew/lib/lib${link_name}.dylib" \
    "/usr/lib/lib${link_name}.dylib"
}

generate_owned_bindings() {
  local header="$1"
  local library="$2"
  local link_name="$3"
  local dylib="$4"
  local output="$5"
  shift 5

  "${BG[@]}" "$header" \
    --library "$library" \
    --link-name "$link_name" \
    --link-mode owned-dl-handle \
    --library-path "$dylib" \
    --emit-layout-tests \
    --layout-test-output "${output%.mojo}_layout_tests.mojo" \
    "$@" \
    --output "$output"
}

build_smoke() {
  local source="$1"
  local output="${2:-${source%.mojo}}"
  "${MOJO[@]}" build "$source" -I "$HERE" -o "$output"
}

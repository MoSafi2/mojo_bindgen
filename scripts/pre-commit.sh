#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v pixi >/dev/null 2>&1; then
  RUNNER=(pixi run)
else
  echo "pre-commit: pixi is required for this repository hook" >&2
  exit 1
fi

echo "pre-commit: formatting"
"${RUNNER[@]}" format

echo "pre-commit: applying safe lint fixes"
"${RUNNER[@]}" ruff check --fix mojo_bindgen tests

echo "pre-commit: restaging formatted and lint-fixed changes"
git add -A

echo "pre-commit: linting"
"${RUNNER[@]}" lint

echo "pre-commit: running light tests"
"${RUNNER[@]}" test-light

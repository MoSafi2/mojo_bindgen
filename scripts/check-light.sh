#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v pixi >/dev/null 2>&1; then
  RUNNER=(pixi run)
else
  echo "check-light: pixi is required for repository validation" >&2
  exit 1
fi

echo "check-light: verifying formatting"
"${RUNNER[@]}" format-check

echo "check-light: linting"
"${RUNNER[@]}" lint

echo "check-light: type checking"
"${RUNNER[@]}" typecheck

echo "check-light: running light tests"
"${RUNNER[@]}" test-light

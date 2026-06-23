#!/usr/bin/env bash
set -euo pipefail
BASE="mojo -I . -I .pixi/envs/default/lib/mojo"
echo "=== parsing/frontend ==="
$BASE tests/mojo/parsing/test_frontend.mojo
echo "=== parsing/diagnostics ==="
$BASE tests/mojo/parsing/test_diagnostics.mojo
echo "=== parsing/doc_comments ==="
$BASE tests/mojo/parsing/test_doc_comments.mojo
echo "=== parsing/registry ==="
$BASE tests/mojo/parsing/test_registry.mojo
echo "=== parsing/target_abi ==="
$BASE tests/mojo/parsing/test_target_abi.mojo
echo "=== All parsing tests pass ==="

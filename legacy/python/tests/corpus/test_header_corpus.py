"""Parser/IR corpus tests for normal and weird header shapes."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.serde import encode_cir
from tests._paths import ROOT as _SHARED_ROOT
from tests.header_harness import HeaderHarness, HeaderParseError

_REPO_ROOT = _SHARED_ROOT
_CORPUS_ROOT = _REPO_ROOT / "tests" / "corpus" / "headers"


def _case_dirs() -> list[Path]:
    return sorted(p for p in _CORPUS_ROOT.iterdir() if p.is_dir())


def _matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _matches(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_matches(a, b) for a, b in zip(actual, expected, strict=True))
        )
    return actual == expected


def _subset_match(actual: Any, expected: Any) -> None:
    assert _matches(actual, expected), (actual, expected)


def _find_decl(decls: list[dict[str, Any]], selector: dict[str, Any]) -> dict[str, Any]:
    matches = [decl for decl in decls if _matches(decl, selector)]
    assert len(matches) == 1, selector
    return matches[0]


def _resolve_path(value: Any, path: str) -> Any:
    cur = value
    for segment in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(segment)]
        else:
            cur = cur[segment]
    return cur


def _expect_phase_pass(status: str) -> bool:
    return status == "pass"


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_header_corpus_case(case_dir: Path, bindgen: HeaderHarness) -> None:
    status = json.loads((case_dir / "status.json").read_text(encoding="utf-8"))
    expect = json.loads((case_dir / "expect.ir.json").read_text(encoding="utf-8"))
    header = case_dir / "input.h"
    try:
        unit = bindgen.parse_header(header, library=case_dir.name, link_name=case_dir.name)
    except HeaderParseError:
        if _expect_phase_pass(status["parse"]):
            raise
        pytest.xfail(f"parse is expected to stay {status['parse']}")
    if not _expect_phase_pass(status["parse"]):
        pytest.fail(f"unexpected parse success for case marked {status['parse']}")
    data = encode_cir(unit)["fields"]
    if not _expect_phase_pass(status["ir"]):
        pytest.fail(f"unexpected IR success for case marked {status['ir']}")
    kind_counts = Counter(decl["kind"] for decl in data["decls"])
    for kind, count in expect["decl_kind_counts"].items():
        assert kind_counts[kind] >= count
    for decl_expect in expect["decls"]:
        decl = _find_decl(data["decls"], {k: v for k, v in decl_expect.items() if k != "attrs"})
        _subset_match(decl, decl_expect.get("attrs", {}))
    for path_expect in expect.get("paths", []):
        decl = _find_decl(data["decls"], path_expect["selector"])
        actual = _resolve_path(decl, path_expect["path"])
        _subset_match(actual, path_expect["attrs"])
    if status["emit"] == "not_required":
        return
    try:
        generated = bindgen.generate(unit, MojoEmitOptions())
    except Exception:
        if _expect_phase_pass(status["emit"]):
            raise
        pytest.xfail(f"emit is expected to stay {status['emit']}")
    if not _expect_phase_pass(status["emit"]):
        pytest.fail(f"unexpected emit success for case marked {status['emit']}")
    assert generated.strip()

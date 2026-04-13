"""Parser/IR corpus tests for normal and weird header shapes."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from mojo_bindgen.codegen.generator import MojoGenerator
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.parsing.parser import ClangParser

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORPUS_ROOT = _REPO_ROOT / "tests" / "corpus" / "headers"


def _has_libclang() -> bool:
    try:
        import clang.cindex  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _has_libclang(),
    reason="libclang not available (use pixi run)",
)


def _case_dirs() -> list[Path]:
    return sorted(p for p in _CORPUS_ROOT.iterdir() if p.is_dir())


def _subset_match(actual: Any, expected: Any) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        for key, value in expected.items():
            assert key in actual, key
            _subset_match(actual[key], value)
        return
    assert actual == expected


def _find_decl(decls: list[dict[str, Any]], selector: dict[str, Any]) -> dict[str, Any]:
    matches = []
    for decl in decls:
        if all(decl.get(key) == value for key, value in selector.items()):
            matches.append(decl)
    assert matches, f"no decl matched {selector}"
    assert len(matches) == 1, f"multiple decls matched {selector}"
    return matches[0]


def _resolve_path(value: Any, path: str) -> Any:
    cur = value
    for segment in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(segment)]
        else:
            cur = cur[segment]
    return cur


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_header_corpus_case(case_dir: Path) -> None:
    status = json.loads((case_dir / "status.json").read_text(encoding="utf-8"))
    expect = json.loads((case_dir / "expect.ir.json").read_text(encoding="utf-8"))

    header = case_dir / "input.h"
    parser = ClangParser(header, library=case_dir.name, link_name=case_dir.name)
    unit = parser.run()
    data = unit.to_json_dict()

    assert status["parse"] == "pass"
    assert status["ir"] == "pass"

    kind_counts = Counter(decl["kind"] for decl in data["decls"])
    assert dict(kind_counts) == expect["decl_kind_counts"]

    for decl_expect in expect["decls"]:
        decl = _find_decl(
            data["decls"],
            {k: v for k, v in decl_expect.items() if k != "attrs"},
        )
        _subset_match(decl, decl_expect.get("attrs", {}))

    for path_expect in expect.get("paths", []):
        decl = _find_decl(data["decls"], path_expect["selector"])
        actual = _resolve_path(decl, path_expect["path"])
        _subset_match(actual, path_expect["attrs"])

    if status["emit"] == "pass":
        generated = MojoGenerator(MojoEmitOptions()).generate(unit)
        assert generated.strip()


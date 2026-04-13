"""Round-trip tests for broad stress headers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


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


@pytest.mark.parametrize(
    ("rel_path", "library", "link_name"),
    [
        ("tests/stress/normal/stress_normal_input.h", "stress_normal", "stress_normal"),
        ("tests/stress/weird/stress_weird_input.h", "stress_weird", "stress_weird"),
    ],
)
def test_stress_fixture_json_stable(rel_path: str, library: str, link_name: str) -> None:
    from mojo_bindgen.ir import Unit
    from mojo_bindgen.parsing.parser import ClangParser

    header = _REPO_ROOT / rel_path
    parser = ClangParser(
        header,
        library=library,
        link_name=link_name,
    )
    unit = parser.run()
    d0 = unit.to_json_dict()
    text = json.dumps(d0)
    d1 = json.loads(text)
    unit2 = Unit.from_json_dict(d1)
    d2 = unit2.to_json_dict()
    assert d0 == d2

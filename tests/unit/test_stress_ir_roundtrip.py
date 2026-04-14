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
        ("tests/stress/weird/stress_macros_input.h", "stress_macros", "stress_macros"),
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


def test_macro_stress_fixture_preserves_supported_and_skips_unsupported() -> None:
    from mojo_bindgen.ir import Const
    from mojo_bindgen.parsing.parser import ClangParser

    header = _REPO_ROOT / "tests" / "stress" / "weird" / "stress_macros_input.h"
    unit = ClangParser(header, library="stress_macros", link_name="stress_macros").run()

    const_names = {decl.name for decl in unit.decls if isinstance(decl, Const)}

    assert {
        "MACRO_INT",
        "MACRO_FLOAT",
        "MACRO_HEX_FLOAT",
        "MACRO_LDOUBLE",
        "MACRO_STRING",
        "MACRO_CHAR",
        "MACRO_NULL",
        "MACRO_REF",
        "MACRO_FWD_REF",
        "MACRO_LATER",
        "MACRO_LINE",
        "MACRO_FILE",
        "MACRO_DATE",
        "MACRO_COUNTER",
        "MACRO_SELF",
        "MACRO_NEG",
        "MACRO_NOT",
        "MACRO_OR",
        "MACRO_SHIFT",
        "MACRO_COMPLEX_INT",
        "MACRO_ADD3",
    } <= const_names

    assert {
        "MACRO_EMPTY",
        "MACRO_TYPE",
        "MACRO_SIZEOF",
        "MACRO_CAST",
        "MACRO_TERNARY",
        "MACRO_COND",
        "MACRO_ASSIGN",
        "MACRO_COMMA",
        "MACRO_CONCAT_STR",
        "MACRO_ATTR",
        "MACRO_DECLSPEC",
        "MACRO_FUNC",
        "MACRO_VA",
        "MACRO_VA_GNU",
        "MACRO_VA_OPT",
        "MACRO_CAT",
        "MACRO_STR",
        "MACRO_GENERIC",
    }.isdisjoint(const_names)

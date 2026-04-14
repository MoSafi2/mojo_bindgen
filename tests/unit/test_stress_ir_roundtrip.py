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


def test_macro_stress_fixture_preserves_supported_and_unsupported() -> None:
    from mojo_bindgen.ir import MacroDecl
    from mojo_bindgen.parsing.parser import ClangParser

    header = _REPO_ROOT / "tests" / "stress" / "weird" / "stress_macros_input.h"
    unit = ClangParser(header, library="stress_macros", link_name="stress_macros").run()

    macros = {decl.name: decl for decl in unit.decls if isinstance(decl, MacroDecl)}

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
        "MACRO_TIME",
        "MACRO_COUNTER",
        "MACRO_STDC",
        "MACRO_STDC_VERSION",
        "MACRO_STDC_HOSTED",
        "MACRO_STDC_NO_ATOMICS",
        "MACRO_STDC_IEC_60559_BFP",
        "MACRO_STDC_VERSION_STDIO_H",
        "MACRO_SELF",
        "MACRO_NEG",
        "MACRO_NOT",
        "MACRO_OR",
        "MACRO_SHIFT",
        "MACRO_COMPLEX_INT",
        "MACRO_ADD3",
    } <= macros.keys()

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
    } <= macros.keys()

    assert macros["MACRO_INT"].kind == "object_like_supported"
    assert macros["MACRO_INT"].expr is not None
    assert macros["MACRO_FILE"].kind == "predefined"
    assert macros["MACRO_FILE"].expr is None
    assert macros["MACRO_FILE"].tokens == ["__FILE__"]
    assert macros["MACRO_STDC_VERSION"].kind == "predefined"
    assert macros["MACRO_STDC_VERSION"].tokens == ["__STDC_VERSION__"]
    assert macros["MACRO_STDC_NO_ATOMICS"].kind == "predefined"
    assert macros["MACRO_STDC_IEC_60559_BFP"].kind == "predefined"
    assert macros["MACRO_STDC_VERSION_STDIO_H"].kind == "predefined"
    assert macros["MACRO_EMPTY"].kind == "empty"
    assert macros["MACRO_EMPTY"].tokens == []
    assert macros["MACRO_FUNC"].kind == "function_like_unsupported"
    assert macros["MACRO_FUNC"].diagnostic is not None
    assert macros["MACRO_GENERIC"].kind == "object_like_unsupported"
    assert macros["MACRO_GENERIC"].diagnostic is not None


def test_weird_stress_fixture_preserves_selected_hard_declarations() -> None:
    from mojo_bindgen.ir import Enum, Function, GlobalVar, Struct, Typedef
    from mojo_bindgen.parsing.parser import ClangParser

    header = _REPO_ROOT / "tests" / "stress" / "weird" / "stress_weird_input.h"
    unit = ClangParser(header, library="stress_weird", link_name="stress_weird").run()

    names = {decl.name for decl in unit.decls if isinstance(decl, (Struct, Function, GlobalVar, Enum, Typedef))}

    assert {
        "ev_flex_old",
        "ev_nested_anon",
        "ev_anon_matryoshka",
        "ev_anon_bits",
        "ev_only_bits",
        "ev_cacheline",
        "ev_fp_returning_arr",
        "ev_dispatch_table",
        "ev_fp_ptr",
        "ev_cv_ptr",
        "ev_const_ptr",
        "ev_const_both",
        "ev_atomic_int",
        "ev_atomic_u64",
        "ev_concurrent",
        "ev_signed_enum",
        "ev_computed",
        "ev_sparse",
        "ev_die",
        "ev_exported",
        "ev_old",
        "ev_nonnull",
        "ev_pair",
        "ev_cstring",
        "ev_vreg",
        "ev_log",
        "ev_vla_fn",
        "ev_static_arr",
        "ev_defaults",
        "ev_default_event",
        "ev_default_event_value",
        "ev_typeof_ptr",
    } <= names

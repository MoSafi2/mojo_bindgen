"""Round-trip tests for IR JSON (deserialize → serialize). Requires libclang."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_everything_fixture_json_stable() -> None:
    from mojo_bindgen.ir import Unit
    from mojo_bindgen.parser import ClangParser

    header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
    parser = ClangParser(
        header,
        library="everything",
        link_name="everything",
    )
    unit = parser.run()
    d0 = unit.to_json_dict()
    text = json.dumps(d0)
    d1 = json.loads(text)
    unit2 = Unit.from_json_dict(d1)
    d2 = unit2.to_json_dict()
    assert d0 == d2


def test_minimal_types_from_json() -> None:
    from mojo_bindgen.ir import EnumRef, Opaque, Primitive, StructRef, TypeRef

    assert isinstance(
        Primitive.from_json_dict(
            {
                "kind": "Primitive",
                "primitive_kind": "INT",
                "name": "int",
                "is_signed": True,
                "size_bytes": 4,
            }
        ),
        Primitive,
    )
    assert isinstance(
        Opaque.from_json_dict({"kind": "Opaque", "name": "FILE"}),
        Opaque,
    )
    r = StructRef.from_json_dict(
        {
            "kind": "StructRef",
            "name": "Foo",
            "c_name": "Foo",
            "is_union": False,
            "size_bytes": 0,
        }
    )
    assert isinstance(r, StructRef)
    er = EnumRef.from_json_dict(
        {
            "kind": "EnumRef",
            "name": "mode_t",
            "c_name": "mode_t",
            "underlying": {
                "kind": "Primitive",
                "primitive_kind": "INT",
                "name": "unsigned int",
                "is_signed": False,
                "size_bytes": 4,
            },
        }
    )
    assert isinstance(er, EnumRef)
    assert er.name == "mode_t"
    tr = TypeRef.from_json_dict(
        {
            "kind": "TypeRef",
            "name": "size_t",
            "canonical": {
                "kind": "Primitive",
                "primitive_kind": "INT",
                "name": "unsigned long",
                "is_signed": False,
                "size_bytes": 8,
            },
        }
    )
    assert isinstance(tr, TypeRef)
    assert tr.name == "size_t"


def test_unknown_type_kind_raises() -> None:
    from mojo_bindgen.ir import type_from_json

    with pytest.raises(ValueError) as exc_info:
        type_from_json({"kind": "NoSuchType"})
    assert "NoSuchType" in str(exc_info.value)

"""Round-trip tests for focused IR JSON helpers."""

from __future__ import annotations

import pytest


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


def test_minimal_types_from_json() -> None:
    from mojo_bindgen.ir import EnumRef, OpaqueRecordRef, Primitive, StructRef, TypeRef

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
        OpaqueRecordRef.from_json_dict(
            {
                "kind": "OpaqueRecordRef",
                "decl_id": "struct:FILE",
                "name": "FILE",
                "c_name": "FILE",
                "is_union": False,
            }
        ),
        OpaqueRecordRef,
    )
    r = StructRef.from_json_dict(
        {
            "kind": "StructRef",
            "decl_id": "struct:Foo",
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
            "decl_id": "enum:mode_t",
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
            "decl_id": "typedef:size_t",
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

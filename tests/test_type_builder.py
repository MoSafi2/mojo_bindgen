"""Tests for context-aware type lowering through ClangParser."""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.ir import EnumRef, Function, Primitive, Struct, TypeRef
from mojo_bindgen.parser import ClangParser


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


def test_type_context_field_param_return_typedef(tmp_path: Path) -> None:
    header = tmp_path / "type_builder_ctx.h"
    header.write_text(
        (
            "typedef unsigned int my_uint;\n"
            "typedef enum mode_t { MODE_A = 1 } mode_t;\n"
            "typedef struct payload_t {\n"
            "  my_uint value;\n"
            "  mode_t mode;\n"
            "} payload_t;\n"
            "mode_t take_mode(my_uint input);\n"
        ),
        encoding="utf-8",
    )
    parser = ClangParser(
        header=header,
        library="ctx",
        link_name="ctx",
        compile_args=[],
    )
    unit = parser.run()

    payload = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "payload_t")
    fn = next(d for d in unit.decls if isinstance(d, Function) and d.name == "take_mode")

    # FIELD context: typedefs lower to canonical representation.
    assert isinstance(payload.fields[0].type, Primitive)
    assert payload.fields[0].type.name == "unsigned int"
    assert isinstance(payload.fields[1].type, EnumRef)
    assert payload.fields[1].type.name == "mode_t"

    # PARAM / RETURN context: typedef names are preserved as TypeRef.
    assert isinstance(fn.ret, TypeRef)
    assert fn.ret.name == "mode_t"
    assert isinstance(fn.ret.canonical, EnumRef)
    assert isinstance(fn.params[0].type, TypeRef)
    assert fn.params[0].type.name == "my_uint"
    assert isinstance(fn.params[0].type.canonical, Primitive)

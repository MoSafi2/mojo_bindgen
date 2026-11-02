"""Mojo 1.2 mapping, eligibility, and additive IR contracts."""

from pathlib import Path

import pytest

from mojo_bindgen import BindgenOptions, bindgen
from mojo_bindgen.analysis.facts.type_layout import type_layout
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    AtomicType,
    BuiltinType,
    FunctionDecl,
    FunctionKind,
    IntKind,
    IntType,
    MojoBuiltin,
    NamedType,
    OpaqueStorageType,
    ParametricBase,
    ParametricType,
    TypeArg,
)
from mojo_bindgen.serde import decode_node, to_debug_dict
from tests.bindgen_helpers import DEFAULT_TARGET_QUERIES


def test_atomic_layout_is_not_assumed_transparent() -> None:
    value = IntType(IntKind.INT, 4, 4)
    atomic = AtomicType(value, size_bytes=16, align_bytes=16)
    assert type_layout(atomic) == (16, 16)
    assert MapTypePass(queries=DEFAULT_TARGET_QUERIES).run(atomic) == OpaqueStorageType(16, 16)
    compatible = AtomicType(value, size_bytes=4, align_bytes=4)
    assert MapTypePass(queries=DEFAULT_TARGET_QUERIES).run(compatible) == ParametricType(
        ParametricBase.ATOMIC, (TypeArg(BuiltinType(MojoBuiltin.C_INT)),)
    )
    assert decode_node(to_debug_dict(atomic), AtomicType) == atomic
    assert decode_node(
        {"kind": "AtomicType", "fields": {"value_type": to_debug_dict(value)}}, AtomicType
    ) == AtomicType(value)


@pytest.mark.parametrize(
    ("target", "flag", "plain"),
    [
        ("x86_64-unknown-linux-gnu", None, BuiltinType(MojoBuiltin.C_CHAR)),
        ("aarch64-unknown-linux-gnu", None, BuiltinType(MojoBuiltin.C_CHAR)),
        ("arm64-apple-macosx", None, BuiltinType(MojoBuiltin.C_CHAR)),
        ("x86_64-unknown-linux-gnu", "-funsigned-char", NamedType("UInt8")),
        ("aarch64-unknown-linux-gnu", "-fsigned-char", NamedType("Int8")),
    ],
)
def test_plain_and_explicit_char_signedness(tmp_path: Path, target, flag, plain) -> None:
    header = tmp_path / "chars.h"
    header.write_text("void chars(char a, signed char b, unsigned char c);\n")
    args = [f"--target={target}"] + ([flag] if flag else [])
    result = bindgen(BindgenOptions(header=header, compile_args=args))
    function = next(d for d in result.mojo_module.decls if isinstance(d, FunctionDecl))
    assert [p.type for p in function.params] == [
        plain,
        BuiltinType(MojoBuiltin.INT8),
        BuiltinType(MojoBuiltin.C_UCHAR),
    ]
    assert result.unit.target_abi.target_triple


@pytest.mark.parametrize("count", [None, 0, 2])
def test_variadic_metadata_roundtrips_current_ir(count) -> None:
    function = FunctionDecl("example", "example", num_fixed_args=count)
    payload = to_debug_dict(function)
    assert decode_node(payload, FunctionDecl) == function
    assert payload["fields"]["num_fixed_args"] == count


def test_non_register_return_and_inline_variadic_are_stubs(tmp_path: Path) -> None:
    header = tmp_path / "calls.h"
    header.write_text(
        "struct Payload { int data[4]; };\nstruct Payload make(void);\ninline int local(int n, ...);\n"
    )
    result = bindgen(BindgenOptions(header=header))
    functions = {d.name: d for d in result.mojo_module.decls if isinstance(d, FunctionDecl)}
    assert functions["make"].kind == FunctionKind.EXTERN_DECLARATION
    assert functions["local"].kind == FunctionKind.DIRECTIVE_STUB
    assert '@extern("make")' in result.bindings_source
    assert "def local(" not in result.bindings_source


def test_variadic_link_mode_policy_and_current_keywords(tmp_path: Path) -> None:
    header = tmp_path / "calls.h"
    header.write_text("int match(int n, ...);\n")
    direct = bindgen(BindgenOptions(header=header))
    dynamic = bindgen(BindgenOptions(header=header, linking="owned_dl_handle"))
    assert "def match_[*_BindgenArgs: AnyType]" in direct.bindings_source
    assert "num_fixed_args=1" in direct.bindings_source
    function = next(d for d in dynamic.mojo_module.decls if isinstance(d, FunctionDecl))
    assert function.kind == FunctionKind.VARIADIC_STUB
    assert "OwnedDLHandle does not expose variadic" in dynamic.bindings_source

"""Tests for standalone MojoIR pretty-printing."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from mojo_bindgen.codegen.mojo_ir_printer import MojoIRPrintOptions, render_mojo_module
from mojo_bindgen.ir import BinaryExpr, IntLiteral
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    ArrayType,
    BitfieldField,
    BitfieldGroupMember,
    BuiltinType,
    CallTarget,
    EnumMember,
    FunctionDecl,
    FunctionKind,
    FunctionType,
    GlobalDecl,
    GlobalKind,
    Initializer,
    InitializerParam,
    LinkMode,
    MojoBuiltin,
    MojoModule,
    NamedType,
    Param,
    ParametricType,
    PointerMutability,
    PointerType,
    StoredMember,
    StructDecl,
    StructKind,
    StructTraits,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_struct_decl_enum_roundtrip_keeps_underlying_type() -> None:
    decl = StructDecl(
        name="Flags",
        kind=StructKind.ENUM,
        underlying_type=BuiltinType(MojoBuiltin.C_INT),
        enum_members=[EnumMember(name="READY", value=1)],
    )

    raw = decl.to_json_dict()
    restored = StructDecl.from_json_dict(raw)

    assert raw["underlying_type"] == {"kind": "BuiltinType", "name": "c_int"}
    assert restored.underlying_type == BuiltinType(MojoBuiltin.C_INT)


def test_render_mojo_module_external_surface_with_synthesized_callback_aliases() -> None:
    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
        decls=[
            StructDecl(
                name="Flags",
                kind=StructKind.ENUM,
                traits=[
                    StructTraits.COPYABLE,
                    StructTraits.MOVABLE,
                    StructTraits.REGISTER_PASSABLE,
                ],
                underlying_type=BuiltinType(MojoBuiltin.C_INT),
                enum_members=[
                    EnumMember(name="READY", value=1),
                    EnumMember(name="ERROR", value=2),
                ],
            ),
            StructDecl(
                name="Widget",
                align=4,
                traits=[StructTraits.COPYABLE, StructTraits.MOVABLE],
                members=[
                    StoredMember(name="count", type=BuiltinType(MojoBuiltin.C_INT), byte_offset=0),
                    StoredMember(
                        name="handler",
                        type=PointerType(
                            pointee=FunctionType(
                                params=[BuiltinType(MojoBuiltin.C_INT)],
                                ret=BuiltinType(MojoBuiltin.C_INT),
                            ),
                            mutability=PointerMutability.MUT,
                        ),
                        byte_offset=8,
                    ),
                    BitfieldGroupMember(
                        storage_name="__bf0",
                        storage_type=BuiltinType(MojoBuiltin.C_UINT),
                        byte_offset=16,
                        fields=[
                            BitfieldField(
                                name="enabled",
                                logical_type=BuiltinType(MojoBuiltin.BOOL),
                                bit_offset=128,
                                bit_width=1,
                                signed=False,
                                bool_semantics=True,
                            ),
                            BitfieldField(
                                name="mode",
                                logical_type=BuiltinType(MojoBuiltin.C_UINT),
                                bit_offset=129,
                                bit_width=3,
                                signed=False,
                            ),
                        ],
                    ),
                ],
                initializers=[
                    Initializer(
                        params=[
                            InitializerParam(
                                name="count",
                                type=BuiltinType(MojoBuiltin.C_INT),
                            ),
                            InitializerParam(
                                name="enabled",
                                type=BuiltinType(MojoBuiltin.BOOL),
                            ),
                        ]
                    )
                ],
            ),
            AliasDecl(
                name="Packet",
                kind=AliasKind.UNION_LAYOUT,
                type_value=ParametricType(base="UnsafeUnion", args=["c_int", "Widget"]),
            ),
            AliasDecl(
                name="LIMIT",
                kind=AliasKind.CONST_VALUE,
                const_value=BinaryExpr(op="+", lhs=IntLiteral(1), rhs=IntLiteral(2)),
            ),
            FunctionDecl(
                name="install",
                link_name="install",
                params=[
                    Param(
                        name="cb",
                        type=PointerType(
                            pointee=FunctionType(
                                params=[BuiltinType(MojoBuiltin.C_INT)],
                                ret=BuiltinType(MojoBuiltin.C_INT),
                            ),
                            mutability=PointerMutability.MUT,
                        ),
                    ),
                    Param(
                        name="widget",
                        type=PointerType(
                            pointee=NamedType("Widget"),
                            mutability=PointerMutability.IMMUT,
                        ),
                    ),
                ],
                return_type=BuiltinType(MojoBuiltin.NONE),
                kind=FunctionKind.WRAPPER,
                call_target=CallTarget(link_mode=LinkMode.EXTERNAL_CALL, symbol="install"),
            ),
        ],
    )

    out = render_mojo_module(module, MojoIRPrintOptions(module_comment=False))

    assert "from std.ffi import external_call, UnsafeUnion, c_int, c_uint" in out
    assert "@align(4)" in out
    assert "struct Flags(Copyable, Movable, RegisterPassable):" in out
    assert "var value: c_int" in out
    assert "comptime READY = Self(c_int(1))" in out
    assert 'comptime Widget_handler_cb = def (arg0: c_int) thin abi("C") -> c_int' in out
    assert "var handler: UnsafePointer[Widget_handler_cb, MutExternalOrigin]" in out
    assert "def enabled(self) -> Bool:" in out
    assert "def set_enabled(mut self, value: Bool):" in out
    assert "comptime Packet = UnsafeUnion[c_int, Widget]" in out
    assert "comptime LIMIT = (1 + 2)" in out
    assert (
        'def install(cb: UnsafePointer[install_cb, MutExternalOrigin], widget: UnsafePointer[Widget, ImmutExternalOrigin]) abi("C") -> None:'
        in out
    )


@pytest.mark.skipif(shutil.which("pixi") is None, reason="requires pixi with mojo toolchain")
def test_rendered_mojo_module_compiles_with_mixed_decl_kinds(tmp_path: Path) -> None:
    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.OWNED_DL_HANDLE,
        decls=[
            AliasDecl(
                name="binary_cb_t",
                kind=AliasKind.CALLBACK_SIGNATURE,
                type_value=FunctionType(
                    params=[
                        BuiltinType(MojoBuiltin.C_INT),
                        PointerType(pointee=None, mutability=PointerMutability.MUT),
                    ],
                    ret=BuiltinType(MojoBuiltin.C_INT),
                ),
            ),
            StructDecl(
                name="Flags",
                kind=StructKind.ENUM,
                traits=[
                    StructTraits.COPYABLE,
                    StructTraits.MOVABLE,
                    StructTraits.REGISTER_PASSABLE,
                ],
                underlying_type=BuiltinType(MojoBuiltin.C_INT),
                enum_members=[EnumMember(name="READY", value=1)],
            ),
            StructDecl(
                name="Widget",
                traits=[StructTraits.COPYABLE, StructTraits.MOVABLE],
                members=[
                    StoredMember(name="count", type=BuiltinType(MojoBuiltin.C_INT), byte_offset=0),
                    StoredMember(
                        name="callback",
                        type=PointerType(
                            pointee=FunctionType(
                                params=[BuiltinType(MojoBuiltin.C_INT)],
                                ret=BuiltinType(MojoBuiltin.C_INT),
                            ),
                            mutability=PointerMutability.MUT,
                        ),
                        byte_offset=8,
                    ),
                    StoredMember(
                        name="buffer",
                        type=ArrayType(element=BuiltinType(MojoBuiltin.C_UCHAR), count=16),
                        byte_offset=16,
                    ),
                ],
            ),
            AliasDecl(
                name="Value",
                kind=AliasKind.TYPE_ALIAS,
                type_value=ParametricType(base="SIMD", args=["DType.float32", "4"]),
            ),
            GlobalDecl(
                name="global_counter",
                link_name="global_counter",
                value_type=BuiltinType(MojoBuiltin.C_INT),
                is_const=False,
                kind=GlobalKind.WRAPPER,
            ),
            FunctionDecl(
                name="install",
                link_name="install",
                params=[
                    Param(
                        name="cb",
                        type=PointerType(
                            pointee=NamedType("binary_cb_t"),
                            mutability=PointerMutability.MUT,
                        ),
                    ),
                ],
                return_type=BuiltinType(MojoBuiltin.NONE),
                kind=FunctionKind.WRAPPER,
                call_target=CallTarget(link_mode=LinkMode.EXTERNAL_CALL, symbol="install"),
            ),
            FunctionDecl(
                name="load_widget",
                link_name="load_widget",
                params=[],
                return_type=PointerType(
                    pointee=NamedType("Widget"),
                    mutability=PointerMutability.MUT,
                ),
                kind=FunctionKind.WRAPPER,
                call_target=CallTarget(link_mode=LinkMode.OWNED_DL_HANDLE, symbol="load_widget"),
            ),
        ],
    )

    rendered = render_mojo_module(module, MojoIRPrintOptions(module_comment=False))
    module_path = tmp_path / "demo_bindings.mojo"
    runner_path = tmp_path / "runner.mojo"
    output_path = tmp_path / "runner_bin"
    module_path.write_text(rendered, encoding="utf-8")
    runner_path.write_text(
        "from demo_bindings import *\n\ndef main():\n    pass\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "pixi",
            "run",
            "mojo",
            "build",
            str(runner_path),
            "-I",
            str(tmp_path),
            "-o",
            str(output_path),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert "def _bindgen_dl() raises -> OwnedDLHandle:" in rendered
    assert (
        "struct GlobalVar[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:"
        in rendered
    )
    assert (
        'def install(cb: UnsafePointer[binary_cb_t, MutExternalOrigin]) abi("C") -> None:'
        in rendered
    )
    assert "def load_widget() raises -> UnsafePointer[Widget, MutExternalOrigin]:" in rendered

"""Tests for standalone MojoIR pretty-printing."""

from __future__ import annotations

import importlib
import shutil
import subprocess
from pathlib import Path

import pytest

from mojo_bindgen.analysis import analyze_to_mojo_module
from mojo_bindgen.analysis.normalize_mojo_module import normalize_mojo_module
from mojo_bindgen.codegen.mojo_ir_printer import (
    MojoIRPrinter,
    MojoIRPrintOptions,
    render_mojo_module,
)
from mojo_bindgen.ir import Field, IntKind, IntType, Struct, TargetABI, Unit
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    ArrayType,
    BitfieldField,
    BitfieldGroupMember,
    BuiltinType,
    CallbackParam,
    CallbackType,
    CallTarget,
    ComptimeMember,
    ConstArg,
    DTypeArg,
    FunctionDecl,
    FunctionKind,
    GlobalDecl,
    GlobalKind,
    Initializer,
    InitializerParam,
    LinkMode,
    ModuleImport,
    MojoBinaryExpr,
    MojoBuiltin,
    MojoCallExpr,
    MojoCastExpr,
    MojoIntLiteral,
    MojoModule,
    MojoRefExpr,
    MojoSizeOfExpr,
    NamedType,
    Param,
    ParametricBase,
    ParametricType,
    PointerMutability,
    PointerType,
    StoredMember,
    StructDecl,
    StructKind,
    StructTraits,
    SupportDecl,
    SupportDeclKind,
    TypeArg,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _i32_type() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _abi() -> TargetABI:
    return TargetABI(pointer_size_bytes=8, pointer_align_bytes=8)


def test_enum_struct_roundtrip_keeps_comptime_members() -> None:
    decl = StructDecl(
        name="Flags",
        kind=StructKind.ENUM,
        fieldwise_init=True,
        traits=[StructTraits.COPYABLE, StructTraits.MOVABLE, StructTraits.REGISTER_PASSABLE],
        members=[
            StoredMember(
                index=0,
                name="value",
                type=BuiltinType(MojoBuiltin.C_INT),
                byte_offset=0,
            )
        ],
        comptime_members=[
            ComptimeMember(
                name="READY",
                const_value=MojoCallExpr(
                    callee=MojoRefExpr("Self"),
                    args=[
                        MojoCastExpr(
                            target=BuiltinType(MojoBuiltin.C_INT),
                            expr=MojoIntLiteral(1),
                        )
                    ],
                ),
            )
        ],
    )

    raw = decl.to_json_dict()
    restored = StructDecl.from_json_dict(raw)

    assert raw["struct_kind"] == "enum"
    assert restored.members[0].type == BuiltinType(MojoBuiltin.C_INT)
    assert restored.comptime_members[0].name == "READY"
    assert restored.fieldwise_init is True


def test_struct_decl_roundtrip_keeps_explicit_align_decorator() -> None:
    decl = StructDecl(
        name="Widget",
        align=64,
        align_decorator=16,
        members=[],
    )

    raw = decl.to_json_dict()
    restored = StructDecl.from_json_dict(raw)

    assert raw["align"] == 64
    assert raw["align_decorator"] == 16
    assert restored.align == 64
    assert restored.align_decorator == 16


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
                fieldwise_init=True,
                traits=[
                    StructTraits.COPYABLE,
                    StructTraits.MOVABLE,
                    StructTraits.REGISTER_PASSABLE,
                ],
                members=[
                    StoredMember(
                        index=0,
                        name="value",
                        type=BuiltinType(MojoBuiltin.C_INT),
                        byte_offset=0,
                    )
                ],
                comptime_members=[
                    ComptimeMember(
                        name="READY",
                        const_value=MojoCallExpr(
                            callee=MojoRefExpr("Self"),
                            args=[
                                MojoCastExpr(
                                    target=BuiltinType(MojoBuiltin.C_INT),
                                    expr=MojoIntLiteral(1),
                                )
                            ],
                        ),
                    ),
                    ComptimeMember(
                        name="ERROR",
                        const_value=MojoCallExpr(
                            callee=MojoRefExpr("Self"),
                            args=[
                                MojoCastExpr(
                                    target=BuiltinType(MojoBuiltin.C_INT),
                                    expr=MojoIntLiteral(2),
                                )
                            ],
                        ),
                    ),
                ],
            ),
            StructDecl(
                name="Widget",
                align=4,
                traits=[StructTraits.COPYABLE, StructTraits.MOVABLE],
                members=[
                    StoredMember(
                        index=0,
                        name="count",
                        type=BuiltinType(MojoBuiltin.C_INT),
                        byte_offset=0,
                    ),
                    StoredMember(
                        index=1,
                        name="handler",
                        type=CallbackType(
                            params=[CallbackParam(name="", type=BuiltinType(MojoBuiltin.C_INT))],
                            ret=BuiltinType(MojoBuiltin.C_INT),
                        ),
                        byte_offset=8,
                    ),
                    BitfieldGroupMember(
                        storage_name="__bf0",
                        storage_type=BuiltinType(MojoBuiltin.C_UINT),
                        byte_offset=16,
                        first_index=2,
                        fields=[
                            BitfieldField(
                                index=2,
                                name="enabled",
                                logical_type=BuiltinType(MojoBuiltin.BOOL),
                                bit_offset=128,
                                bit_width=1,
                                signed=False,
                                bool_semantics=True,
                            ),
                            BitfieldField(
                                index=3,
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
                type_value=ParametricType(
                    base=ParametricBase.UNSAFE_UNION,
                    args=[
                        TypeArg(BuiltinType(MojoBuiltin.C_INT)),
                        TypeArg(NamedType("Widget")),
                    ],
                ),
            ),
            AliasDecl(
                name="LIMIT",
                kind=AliasKind.CONST_VALUE,
                const_value=MojoBinaryExpr(
                    op="+",
                    lhs=MojoIntLiteral(1),
                    rhs=MojoIntLiteral(2),
                ),
            ),
            FunctionDecl(
                name="install",
                link_name="install",
                params=[
                    Param(
                        name="cb",
                        type=CallbackType(
                            params=[CallbackParam(name="", type=BuiltinType(MojoBuiltin.C_INT))],
                            ret=BuiltinType(MojoBuiltin.C_INT),
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

    out = render_mojo_module(
        normalize_mojo_module(module),
        MojoIRPrintOptions(module_comment=False),
    )

    assert "from std.ffi import external_call, UnsafeUnion, c_int, c_uint" in out
    assert "@align(4)" in out
    assert "@fieldwise_init\nstruct Flags(Copyable, Movable, RegisterPassable):" in out
    assert "struct Flags(Copyable, Movable, RegisterPassable):" in out
    assert "var value: c_int" in out
    assert "comptime READY = Self(c_int(1))" in out
    assert 'comptime Widget_handler_cb = def (arg0: c_int) thin abi("C") -> c_int' in out
    assert "var handler: Widget_handler_cb" in out
    assert "def enabled(self) -> Bool:" in out
    assert "def set_enabled(mut self, value: Bool):" in out
    assert "comptime Packet = UnsafeUnion[c_int, Widget]" in out
    assert "comptime LIMIT = (1 + 2)" in out
    assert (
        'def install(cb: install_cb, widget: UnsafePointer[Widget, ImmutExternalOrigin]) abi("C") -> None:'
        in out
    )


def test_render_callback_alias_uses_none_in_signature_position() -> None:
    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
        decls=[
            AliasDecl(
                name="log_callback_t",
                kind=AliasKind.CALLBACK_SIGNATURE,
                type_value=CallbackType(
                    params=[
                        CallbackParam(
                            name="msg",
                            type=PointerType(
                                pointee=BuiltinType(MojoBuiltin.C_CHAR),
                                mutability=PointerMutability.IMMUT,
                            ),
                        )
                    ],
                    ret=BuiltinType(MojoBuiltin.NONE),
                ),
            )
        ],
    )

    out = render_mojo_module(
        normalize_mojo_module(module), MojoIRPrintOptions(module_comment=False)
    )

    assert (
        'comptime log_callback_t = def (msg: UnsafePointer[c_char, ImmutExternalOrigin]) thin abi("C") -> None'
        in out
    )


def test_normalize_and_render_sizeof_imports_std_sys_info() -> None:
    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
        decls=[
            AliasDecl(
                name="SIZE",
                kind=AliasKind.CONST_VALUE,
                const_value=MojoSizeOfExpr(target=BuiltinType(MojoBuiltin.C_INT)),
            ),
        ],
    )

    normalized = normalize_mojo_module(module)
    assert ModuleImport(module="std.sys.info", names=["size_of"]) in normalized.imports

    out = render_mojo_module(normalized)
    assert "from std.sys.info import size_of" in out
    assert "comptime SIZE = size_of[c_int]()" in out


def test_normalize_mojo_module_makes_callback_hoisting_and_imports_explicit() -> None:
    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.OWNED_DL_HANDLE,
        decls=[
            StructDecl(
                name="Widget",
                traits=[StructTraits.COPYABLE, StructTraits.MOVABLE],
                members=[
                    StoredMember(
                        index=0,
                        name="handler",
                        type=CallbackType(
                            params=[CallbackParam(name="", type=BuiltinType(MojoBuiltin.C_INT))],
                            ret=BuiltinType(MojoBuiltin.C_INT),
                        ),
                        byte_offset=0,
                    )
                ],
            ),
            GlobalDecl(
                name="global_counter",
                link_name="global_counter",
                value_type=BuiltinType(MojoBuiltin.C_INT),
                is_const=False,
                kind=GlobalKind.WRAPPER,
            ),
        ],
    )

    normalized = normalize_mojo_module(module)

    assert normalized.imports == [
        ModuleImport(
            module="std.ffi",
            names=["DEFAULT_RTLD", "OwnedDLHandle", "c_int"],
        )
    ]
    assert normalized.support_decls == [
        SupportDecl(SupportDeclKind.DL_HANDLE_HELPERS),
        SupportDecl(SupportDeclKind.GLOBAL_SYMBOL_HELPERS),
    ]
    assert isinstance(normalized.decls[0], AliasDecl)
    assert normalized.decls[0].name == "Widget_handler_cb"
    widget = next(decl for decl in normalized.decls if isinstance(decl, StructDecl))
    assert isinstance(widget.members[0], StoredMember)
    assert widget.members[0].type == NamedType("Widget_handler_cb")


def test_render_mojo_module_uses_owned_dl_handle_library_path_hint() -> None:
    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.OWNED_DL_HANDLE,
        library_path_hint="/tmp/libdemo.so",
        decls=[
            FunctionDecl(
                name="install",
                link_name="install",
                params=[],
                return_type=BuiltinType(MojoBuiltin.NONE),
                kind=FunctionKind.WRAPPER,
                call_target=CallTarget(link_mode=LinkMode.OWNED_DL_HANDLE, symbol="install"),
            )
        ],
    )

    rendered = render_mojo_module(
        normalize_mojo_module(module),
        MojoIRPrintOptions(module_comment=False),
    )

    assert 'comptime _BINDGEN_LIB_PATH: String = "/tmp/libdemo.so"' in rendered
    assert "return OwnedDLHandle(_BINDGEN_LIB_PATH)" in rendered


def test_render_mojo_module_does_not_normalize_implicitly(monkeypatch) -> None:
    normalize_mod = importlib.import_module("mojo_bindgen.analysis.normalize_mojo_module")

    def fail(*_args, **_kwargs):
        raise AssertionError("render_mojo_module should not normalize")

    monkeypatch.setattr(normalize_mod, "normalize_mojo_module", fail)

    rendered = render_mojo_module(
        MojoModule(
            source_header="demo.h",
            library="demo",
            link_name="demo",
            link_mode=LinkMode.EXTERNAL_CALL,
            decls=[],
        ),
        MojoIRPrintOptions(module_comment=False),
    )

    assert rendered == ""


def test_normalize_mojo_module_sets_align_decorator_before_printing() -> None:
    normalized = normalize_mojo_module(
        MojoModule(
            source_header="demo.h",
            library="demo",
            link_name="demo",
            link_mode=LinkMode.EXTERNAL_CALL,
            decls=[
                StructDecl(
                    name="Widget",
                    align=8,
                    members=[],
                )
            ],
        )
    )

    widget = next(decl for decl in normalized.decls if isinstance(decl, StructDecl))

    assert widget.align == 8
    assert widget.align_decorator == 8


def test_normalize_and_printer_keep_union_byte_fallback_without_unsafe_union_import() -> None:
    normalized = normalize_mojo_module(
        MojoModule(
            source_header="demo.h",
            library="demo",
            link_name="demo",
            link_mode=LinkMode.EXTERNAL_CALL,
            decls=[
                AliasDecl(
                    name="Dup",
                    kind=AliasKind.UNION_LAYOUT,
                    type_value=ArrayType(
                        element=BuiltinType(MojoBuiltin.UINT8),
                        count=4,
                    ),
                )
            ],
        )
    )

    assert normalized.imports == []

    rendered = MojoIRPrinter(MojoIRPrintOptions(module_comment=False)).render(normalized)

    assert "UnsafeUnion" not in rendered
    assert "comptime Dup = InlineArray[UInt8, 4]" in rendered


def test_printer_uses_explicit_align_decorator_only() -> None:
    rendered = MojoIRPrinter(MojoIRPrintOptions(module_comment=False)).render(
        MojoModule(
            source_header="demo.h",
            library="demo",
            link_name="demo",
            link_mode=LinkMode.EXTERNAL_CALL,
            decls=[
                StructDecl(
                    name="RawAlignOnly",
                    align=8,
                    members=[],
                ),
                StructDecl(
                    name="ExplicitAlign",
                    align=64,
                    align_decorator=16,
                    members=[],
                ),
            ],
        )
    )

    assert "@align(16)" in rendered
    assert "@align(8)" not in rendered
    assert "@align(64)" not in rendered


def test_printer_renders_lowered_struct_layout_members_without_normalize_inference() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Struct(
                decl_id="struct:Aligned",
                name="Aligned",
                c_name="Aligned",
                fields=[
                    Field(
                        name="value",
                        source_name="value",
                        type=_i32_type(),
                        byte_offset=0,
                        size_bytes=4,
                    )
                ],
                size_bytes=16,
                align_bytes=16,
                requested_align_bytes=16,
            ),
            Struct(
                decl_id="struct:Padded",
                name="Padded",
                c_name="Padded",
                fields=[
                    Field(
                        name="tag",
                        source_name="tag",
                        type=IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1),
                        byte_offset=0,
                        size_bytes=1,
                    ),
                    Field(
                        name="value",
                        source_name="value",
                        type=_i32_type(),
                        byte_offset=8,
                        size_bytes=4,
                    ),
                ],
                size_bytes=12,
                align_bytes=4,
            ),
            Struct(
                decl_id="struct:Packed",
                name="Packed",
                c_name="Packed",
                fields=[
                    Field(
                        name="tag",
                        source_name="tag",
                        type=IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1),
                        byte_offset=0,
                        size_bytes=1,
                    ),
                    Field(
                        name="value",
                        source_name="value",
                        type=_i32_type(),
                        byte_offset=1,
                        size_bytes=4,
                    ),
                ],
                size_bytes=5,
                align_bytes=1,
                is_packed=True,
            ),
            Struct(
                decl_id="struct:Flags",
                name="Flags",
                c_name="Flags",
                fields=[
                    Field(
                        name="enabled",
                        source_name="enabled",
                        type=IntType(int_kind=IntKind.BOOL, size_bytes=1, align_bytes=1),
                        byte_offset=0,
                        size_bytes=1,
                        is_bitfield=True,
                        bit_offset=0,
                        bit_width=1,
                    )
                ],
                size_bytes=1,
                align_bytes=1,
            ),
        ],
    )

    lowered = analyze_to_mojo_module(unit)
    aligned = next(
        decl for decl in lowered.decls if isinstance(decl, StructDecl) and decl.name == "Aligned"
    )

    assert aligned.align_decorator == 16

    rendered = MojoIRPrinter(MojoIRPrintOptions(module_comment=False)).render(lowered)

    assert "@align(16)\n@fieldwise_init\nstruct Aligned" in rendered
    assert "var __pad0: InlineArray[UInt8, 4]" in rendered
    assert "var storage: InlineArray[UInt8, 5]" in rendered
    assert "var __bf0: c_uchar" in rendered
    assert "def enabled(self) -> Bool:" in rendered
    assert "def set_enabled(mut self, value: Bool):" in rendered


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
                type_value=CallbackType(
                    params=[
                        CallbackParam(name="arg0", type=BuiltinType(MojoBuiltin.C_INT)),
                        CallbackParam(
                            name="arg1",
                            type=PointerType(pointee=None, mutability=PointerMutability.MUT),
                        ),
                    ],
                    ret=BuiltinType(MojoBuiltin.C_INT),
                ),
            ),
            StructDecl(
                name="Flags",
                kind=StructKind.ENUM,
                fieldwise_init=True,
                traits=[
                    StructTraits.COPYABLE,
                    StructTraits.MOVABLE,
                    StructTraits.REGISTER_PASSABLE,
                ],
                members=[
                    StoredMember(
                        index=0,
                        name="value",
                        type=BuiltinType(MojoBuiltin.C_INT),
                        byte_offset=0,
                    )
                ],
                comptime_members=[
                    ComptimeMember(
                        name="READY",
                        const_value=MojoCallExpr(
                            callee=MojoRefExpr("Self"),
                            args=[
                                MojoCastExpr(
                                    target=BuiltinType(MojoBuiltin.C_INT),
                                    expr=MojoIntLiteral(1),
                                )
                            ],
                        ),
                    )
                ],
            ),
            StructDecl(
                name="Widget",
                traits=[StructTraits.COPYABLE, StructTraits.MOVABLE],
                members=[
                    StoredMember(
                        index=0,
                        name="count",
                        type=BuiltinType(MojoBuiltin.C_INT),
                        byte_offset=0,
                    ),
                    StoredMember(
                        index=1,
                        name="callback",
                        type=CallbackType(
                            params=[CallbackParam(name="", type=BuiltinType(MojoBuiltin.C_INT))],
                            ret=BuiltinType(MojoBuiltin.C_INT),
                        ),
                        byte_offset=8,
                    ),
                    StoredMember(
                        index=2,
                        name="buffer",
                        type=ArrayType(element=BuiltinType(MojoBuiltin.C_UCHAR), count=16),
                        byte_offset=16,
                    ),
                ],
            ),
            AliasDecl(
                name="Value",
                kind=AliasKind.TYPE_ALIAS,
                type_value=ParametricType(
                    base=ParametricBase.SIMD,
                    args=[DTypeArg("DType.float32"), ConstArg(4)],
                ),
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
                        type=NamedType("binary_cb_t"),
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

    rendered = render_mojo_module(
        normalize_mojo_module(module),
        MojoIRPrintOptions(module_comment=False),
    )
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
    assert 'def install(cb: binary_cb_t) abi("C") -> None:' in rendered
    assert "def load_widget() raises -> UnsafePointer[Widget, MutExternalOrigin]:" in rendered

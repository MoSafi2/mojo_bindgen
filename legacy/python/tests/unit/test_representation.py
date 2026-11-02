"""Independent source facts and storage/callability regressions."""

import pytest

from mojo_bindgen.analysis.facts.context import build_analysis_context
from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.analysis.mojo.const_expr_mapping import ConstExprMappingError, MapConstExprPass
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    BuiltinType,
    ByteOrder,
    CFloatLiteral,
    CSizeOfExpr,
    FloatFormat,
    FloatKind,
    FloatType,
    Function,
    FunctionDecl,
    FunctionKind,
    IntKind,
    IntLiteral,
    IntType,
    MojoBuiltin,
    OpaqueStorageMember,
    OpaqueStorageType,
    Struct,
    StructDecl,
    TargetABI,
    Unit,
)
from mojo_bindgen.parsing.parser import ClangParser
from mojo_bindgen.parsing.target_abi import probe_target_abi
from tests.bindgen_helpers import analyze_to_mojo_module, render_mojo_source


def test_clang_float_facts_follow_flags():
    native = probe_target_abi([])
    scalar = next(f for f in native.float_abi if f.kind == FloatKind.LONG_DOUBLE)
    assert scalar.format == FloatFormat.X87_EXTENDED
    assert (scalar.size_bytes, scalar.align_bytes) == (16, 16)
    alternate = probe_target_abi(["-mlong-double-64"])
    scalar = next(f for f in alternate.float_abi if f.kind == FloatKind.LONG_DOUBLE)
    assert scalar.format == FloatFormat.BINARY64
    mapper = MapTypePass(TargetQueries(alternate))
    assert mapper.run(FloatType(FloatKind.LONG_DOUBLE, 8, 8)) == BuiltinType(MojoBuiltin.C_DOUBLE)


def test_extended_values_preserve_storage_without_numeric_operations():
    mapper = MapTypePass(TargetQueries(probe_target_abi([])))
    extended = FloatType(FloatKind.LONG_DOUBLE, 16, 16)
    assert mapper.run(extended) == OpaqueStorageType(16, 16)
    assert not mapper.value_supported(extended)
    expressions = MapConstExprPass(mapper)
    assert expressions.run(CSizeOfExpr(extended)) == IntLiteral(16)
    with pytest.raises(ConstExprMappingError):
        expressions.run(CFloatLiteral("1.0L"))
    assert mapper.run(FloatType(FloatKind.DOUBLE, 8, 16)) == BuiltinType(MojoBuiltin.UNSUPPORTED)


def test_real_max_align_t_and_call_stubs(tmp_path):
    header = tmp_path / "alignment.h"
    header.write_text(
        "#include <stddef.h>\nlong double echo(long double value);\nvoid touch(max_align_t *out);\n"
    )
    unit = ClangParser(header, "alignment", "alignment").run()
    module = analyze_to_mojo_module(unit)
    record = next(d for d in module.decls if isinstance(d, StructDecl) and d.name == "max_align_t")
    assert record.align_decorator == 16
    assert record.members == (OpaqueStorageMember("storage", 32),)
    functions = {d.name: d for d in module.decls if isinstance(d, FunctionDecl)}
    assert functions["echo"].kind == FunctionKind.ABI_STUB
    assert functions["touch"].kind == FunctionKind.WRAPPER
    facts = build_analysis_context(unit)
    source = next(d for d in unit.decls if isinstance(d, Struct) and d.name == "max_align_t")
    assert facts.record_storage[source.decl_id].target_layout == (32, 16)
    text = render_mojo_source(unit)
    assert "callable binding omitted" in text
    assert "var __max_align_ld: c_double" not in text


def test_unknown_call_profile_does_not_claim_host_abi():
    scalar = IntType(IntKind.INT, 4, 4)
    unit = Unit(
        "x.h", "x", "x", TargetABI(8, 8, ByteOrder.LITTLE), (Function("f", "f", scalar, ()),)
    )
    functions = [d for d in analyze_to_mojo_module(unit).decls if isinstance(d, FunctionDecl)]
    assert functions[0].kind == FunctionKind.ABI_STUB


def test_integer_alias_names_cannot_override_source_semantics():
    from mojo_bindgen.analysis.mojo.alias_mapping import map_typedef_alias

    mapper = MapTypePass(TargetQueries(probe_target_abi([])))
    alias = map_typedef_alias(
        c_name="uint32_t", aliased=IntType(IntKind.INT, 4, 4), type_mapper=mapper
    )
    assert alias is not None
    assert alias.type_value == BuiltinType(MojoBuiltin.C_INT)


def test_verified_opaque_children_remain_embeddable(tmp_path):
    from mojo_bindgen.ir import StoredMember

    header = tmp_path / "nested.h"
    header.write_text(
        "struct Inner { long double value; };\nstruct Outer { int tag; struct Inner child; int tail; };\nvoid consume(struct Outer value);\n"
    )
    unit = ClangParser(header, "nested", "nested").run()
    module = analyze_to_mojo_module(unit)
    outer = next(d for d in module.decls if isinstance(d, StructDecl) and d.name == "Outer")
    assert any(isinstance(m, StoredMember) and m.name == "child" for m in outer.members)
    assert (
        next(d for d in module.decls if isinstance(d, FunctionDecl)).kind == FunctionKind.ABI_STUB
    )


def test_unknown_storage_stubs_do_not_abort_other_declarations():
    from mojo_bindgen.ir import GlobalVar, VoidType

    unknown = FloatType(FloatKind.DOUBLE, 8, 16)
    unit = Unit(
        "a.h",
        "a",
        "a",
        probe_target_abi([]),
        (
            Function("bad", "bad", unknown, ()),
            GlobalVar("g", "bad_global", "bad_global", unknown, False),
            Function("good", "good", VoidType(), ()),
        ),
    )
    source = render_mojo_source(unit)
    assert "# <unsupported> bad(" in source
    assert "# global variable bad_global: <unsupported>" in source
    assert "def good(" in source

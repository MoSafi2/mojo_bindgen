"""Publication, context binding, structural validation and exact literal regression tests."""
from std.memory import ArcPointer
from std.testing import assert_equal, assert_true, assert_false, assert_raises, TestSuite
from mojo_bindgen.ir import *
from mojo_bindgen.serde import (
    dumps_cir,
    dumps_mojo_ir,
    loads_cir,
    loads_mojo_ir,
    dumps_c_expr,
    loads_c_expr,
)
from mojo_bindgen.orchestrator import generate_from_unit
from mojo_bindgen.analysis.pipeline import AnalysisOrchestrator
from mojo_bindgen.analysis.facts.context import build_analysis_context
from mojo_bindgen.analysis.mojo.unit_mapping import MapUnitPass
from mojo_bindgen.analysis.mojo.const_expr_mapping import MapConstExprPass
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.analysis.facts.record_layout import analyze_record_layout
from mojo_bindgen.analysis.mojo.record_policies import assign_record_policies
from mojo_bindgen.codegen.normalize_mojo_module import normalize_mojo_module
from mojo_bindgen._numbers import IntegerValue


def _unit() -> Unit:
    return Unit("test.h", "test", "test", TargetABI(8, 8, ByteOrder.LITTLE))


def _int() -> CType:
    return CType.int_type(IntType(IntKind.INT, 4, 4))


def test_backend_fresh_outputs_and_builder_isolation() raises:
    var unit = _unit()
    var fields = List[Field]()
    fields.append(Field("x", "x", ArcPointer(_int()), 0, size_bytes=4))
    unit.decls.append(Decl.struct_decl(Struct("r", "R", "R", fields.copy(), 4, 4)))
    var published = ArcPointer(unit.copy())
    var before = dumps_cir(published.ptr()[])
    fields.append(Field("later", "later", ArcPointer(_int()), 4, size_bytes=4))
    unit.decls.clear()
    var first = generate_from_unit(published.ptr()[], layout_module_name=String("bindings"))
    var second = generate_from_unit(published.ptr()[], layout_module_name=String("bindings"))
    assert_equal(first.bindings_source, second.bindings_source)
    assert_equal(first.layout_test_source.value(), second.layout_test_source.value())
    assert_equal(dumps_cir(published.ptr()[]), before)
    assert_true(first.normalized_unit.ptr() != second.normalized_unit.ptr())
    first.mojo_module.decls.clear()
    assert_equal(len(second.mojo_module.decls), 1)
    assert_equal(dumps_cir(loads_cir(before)), before)
    var target = dumps_mojo_ir(second.mojo_module)
    assert_equal(dumps_mojo_ir(loads_mojo_ir(target)), target)


def test_context_is_bound_to_source_unit() raises:
    var first = _unit()
    var second = _unit()
    first.decls.append(
        Decl.const_decl(
            Const("A", ArcPointer(_int()), ArcPointer(CConstExpr.int_literal(IntLiteral(1))))
        )
    )
    second.decls.append(
        Decl.const_decl(
            Const("B", ArcPointer(_int()), ArcPointer(CConstExpr.int_literal(IntLiteral(2))))
        )
    )
    var a = ArcPointer(first^)
    var b = ArcPointer(second^)
    var context = ArcPointer(build_analysis_context(a))
    var mapper = MapUnitPass(context=context.copy())
    var one = mapper.run(a)
    var two = mapper.run(b)
    assert_true(dumps_mojo_ir(one) != dumps_mojo_ir(two))
    assert_equal(dumps_mojo_ir(mapper.run(a)), dumps_mojo_ir(one))
    assert_true(context.ptr()[].unit.ptr() == a.ptr())


def test_source_expression_cycle_and_failure_recovery() raises:
    var mapper = MapConstExprPass(MapTypePass(TargetQueries(_unit().target_abi.copy())))
    var cycle = ArcPointer(CConstExpr.int_literal(IntLiteral(0)))
    cycle[] = CConstExpr.c_unary_expr(CUnaryExpr("-", cycle.copy()))
    var caught = False
    try:
        _ = mapper.run(cycle.ptr()[])
    except error:
        caught = String(error) == "structural CIR expression cycle"
    cycle[] = CConstExpr.int_literal(IntLiteral(0))
    assert_true(caught)
    with assert_raises():
        _ = mapper.run(CConstExpr.c_null_ptr_literal(CNullPtrLiteral()))
    var good = mapper.run(CConstExpr.int_literal(IntLiteral(42)))
    match good:
        case .int_literal(v):
            assert_equal(v.value.digits, "42")
        case _:
            raise Error("expected integer")


def test_target_cycles_rejected_and_reusable() raises:
    var cycle = ArcPointer(MojoType.builtin_type(BuiltinType(MojoBuiltin.C_INT)))
    cycle[] = MojoType.mojo_array(MojoArray(cycle.copy(), 1))
    var module = MojoModule("x", "x", "x", LinkMode.EXTERNAL_CALL)
    module.decls.append(
        MojoDecl.alias_decl(AliasDecl("Cycle", AliasKind.TYPE_ALIAS, type_value=cycle.copy()))
    )
    var caught = False
    try:
        _ = normalize_mojo_module(module)
    except error:
        caught = String(error) == "structural MojoIR type cycle"
    cycle[] = MojoType.builtin_type(BuiltinType(MojoBuiltin.C_INT))
    assert_true(caught)
    _ = normalize_mojo_module(module)
    var expr = ArcPointer(MojoConstExpr.int_literal(IntLiteral(0)))
    expr[] = MojoConstExpr.mojo_unary_expr(MojoUnaryExpr("-", expr.copy()))
    module.decls.append(
        MojoDecl.alias_decl(AliasDecl("Expr", AliasKind.CONST_VALUE, const_value=expr.copy()))
    )
    caught = False
    try:
        _ = normalize_mojo_module(module)
    except error:
        caught = String(error) == "structural MojoIR expression cycle"
    expr[] = MojoConstExpr.int_literal(IntLiteral(0))
    assert_true(caught)
    _ = normalize_mojo_module(module)


def test_exact_integers_and_geometry_limits() raises:
    var huge = IntegerValue.from_decimal(
        "-000123456789012345678901234567890123456789012345678901234567890"
    )
    assert_equal(huge.digits, "-123456789012345678901234567890123456789012345678901234567890")
    var expr = CConstExpr.int_literal(IntLiteral(huge.copy()))
    assert_equal(dumps_c_expr(loads_c_expr(dumps_c_expr(expr))), dumps_c_expr(expr))
    assert_equal(IntegerValue.from_decimal("-000").digits, "0")
    with assert_raises():
        _ = huge.to_int()
    with assert_raises():
        _ = IntegerValue.from_decimal("1.5")


def test_layout_and_policy_passes_preserve_inputs() raises:
    var fields = List[Field]()
    fields.append(Field("x", "x", ArcPointer(_int()), 0, size_bytes=4))
    var record = Struct("r", "R", "R", fields^, 8, 4)
    var facts = analyze_record_layout(record)
    assert_equal(facts.size_bytes, 8)
    assert_equal(len(facts.padding_spans), 1)
    assert_equal(facts.padding_spans[0].size_bytes, 4)
    var unit = _unit()
    unit.decls.append(Decl.struct_decl(record.copy()))
    var analysis = AnalysisOrchestrator().analyze_pipeline(unit)
    var before = dumps_mojo_ir(analysis.policy_light_module)
    _ = assign_record_policies(analysis.policy_light_module)
    assert_equal(dumps_mojo_ir(analysis.policy_light_module), before)
    var bad = _unit()
    bad.decls.append(Decl.struct_decl(Struct("", "bad", "bad", List[Field](), 0, 1)))
    var orchestrator = AnalysisOrchestrator()
    with assert_raises():
        _ = orchestrator.analyze(bad)
    assert_equal(dumps_mojo_ir(orchestrator.analyze(unit)), dumps_mojo_ir(analysis.mojo_module))


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()

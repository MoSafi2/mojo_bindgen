"""Structural equality, shared analysis and finalized C call contracts."""
from std.memory import ArcPointer
from std.os import abort
from std.testing import TestSuite, assert_equal, assert_true, assert_false, assert_raises
from mojo_bindgen.ir import *
from mojo_bindgen.analysis.pipeline import AnalysisOrchestrator
from mojo_bindgen.analysis.facts.context import build_analysis_context
from mojo_bindgen.analysis.facts.c_abi import CABIQueries
from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.mojo.struct_mapping import StructMappingContext, map_struct
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.codegen.mojo_ir_printer import render_mojo_module
from mojo_bindgen.codegen.normalize_mojo_module import normalize_mojo_module
from mojo_bindgen.orchestrator import generate_from_unit
from mojo_bindgen.serde import dumps_cir, dumps_mojo_ir, loads_mojo_ir


def _block() -> Unit:
    var unit = Unit(
        "block.h",
        "block",
        "block",
        TargetABI(8, 8, ByteOrder.LITTLE, String("x86_64-unknown-linux-gnu")),
    )
    var fields = List[Field]()
    fields.append(
        Field(
            "values",
            "values",
            ArcPointer(
                CType.c_array(
                    CArray(
                        ArcPointer(CType.float_type(FloatType(FloatKind.DOUBLE, 8, 8))),
                        3,
                        size_bytes=24,
                        align_bytes=8,
                    )
                )
            ),
            0,
            size_bytes=24,
        )
    )
    unit.decls.append(Decl.struct_decl(Struct("block", "Block", "Block", fields^, 24, 8)))
    unit.decls.append(
        Decl.function(
            Function(
                "make_block",
                "c_make_block",
                ArcPointer(
                    CType.struct_ref(
                        StructRef(
                            "block",
                            "Block",
                            "Block",
                            size_bytes=24,
                            align_bytes=8,
                        )
                    )
                ),
                List[CParam](),
                decl_id="make_block",
            )
        )
    )
    return unit^


def _kind(module: MojoModule) -> FunctionKind:
    for decl in module.decls:
        if case .function_decl(f) = decl:
            return f.kind
    abort("missing function")


def test_structural_equality_uses_values_across_allocations() raises:
    var a = _block()
    var b = _block()
    assert_true(a == b)
    assert_true(equal(a, b))
    assert_true(equal(a.decls, b.decls))
    if case .function(f) = b.decls[1]:
        var changed = f.copy()
        changed.link_name = "different_symbol"
        b.decls[1] = Decl.function(changed^)
    assert_false(a == b)
    var x = MojoType.mojo_pointer(MojoPointer(ArcPointer(MojoType.named_type(NamedType("X")))))
    var y = MojoType.mojo_pointer(MojoPointer(ArcPointer(MojoType.named_type(NamedType("X")))))
    assert_true(x == y)
    assert_false(x == MojoType.named_type(NamedType("X")))


def test_lean_and_snapshot_analysis_agree() raises:
    var unit = _block()
    var before = dumps_cir(unit)
    var analyzer = AnalysisOrchestrator()
    var snapshots = analyzer.analyze_pipeline(unit)
    var lean = analyzer.analyze_normalized(unit)
    assert_equal(dumps_cir(snapshots.raw_unit[]), before)
    assert_equal(dumps_cir(snapshots.normalized_unit[]), dumps_cir(lean.normalized_unit[]))
    assert_equal(dumps_mojo_ir(snapshots.mojo_module), dumps_mojo_ir(lean.mojo_module))
    assert_equal(dumps_cir(unit), before)
    lean.mojo_module.decls.clear()
    assert_true(len(snapshots.mojo_module.decls) > 0)
    var facts = ArcPointer(build_analysis_context(snapshots.normalized_unit))
    var context = StructMappingContext(facts.copy(), MapTypePass(facts[].target_queries.copy()))
    assert_true(context.facts.ptr() == facts.ptr())
    var records = 0
    for decl in snapshots.normalized_unit[].decls:
        if case .struct_decl(record) = decl:
            var one = map_struct(record, context)
            var two = map_struct(record, context)
            assert_true(one == two)
            one.members.clear()
            assert_equal(len(two.members), 1)
            records += 1
    assert_equal(records, 1)


def test_direct_memory_returns_and_codec() raises:
    var result = generate_from_unit(_block())
    assert_true(_kind(result.mojo_module) == FunctionKind.EXTERN_DECLARATION)
    assert_true('@extern("c_make_block")' in result.bindings_source)
    assert_true('def make_block() abi("C") -> Block:' in result.bindings_source)
    var encoded = dumps_mojo_ir(result.mojo_module)
    assert_equal(dumps_mojo_ir(loads_mojo_ir(encoded)), encoded)
    var options = MojoEmitOptions(linking=LinkMode.OWNED_DL_HANDLE)
    var dynamic = generate_from_unit(_block(), options)
    assert_true(_kind(dynamic.mojo_module) == FunctionKind.NON_REGISTER_RETURN_STUB)
    assert_false("@extern" in dynamic.bindings_source)


def test_memory_return_eligibility_is_conservative() raises:
    for variant in range(5):
        var unit = _block()
        if case .struct_decl(r) = unit.decls[0]:
            var record = r.copy()
            if variant == 0:
                record.is_packed = True
            elif variant == 1:
                record.requested_align_bytes = 16
            elif variant == 2:
                record.is_union = True
            elif variant == 3:
                record.size_bytes = 32
            else:
                record.fields[0].fam_pattern = FamPattern.c99_empty
            unit.decls[0] = Decl.struct_decl(record^)
        var owner = ArcPointer(unit^)
        var queries = CABIQueries(ArcPointer(build_analysis_context(owner)))
        if case .function(f) = owner[].decls[1]:
            assert_false(queries.memory_return_eligible(f))


def test_printer_rejects_unfinalized_or_corrupted_modules() raises:
    var final = generate_from_unit(_block()).mojo_module.copy()
    final.dependencies.imports.clear()
    with assert_raises():
        _ = render_mojo_module(final)
    final = generate_from_unit(_block()).mojo_module.copy()
    if case .function_decl(f) = final.decls[len(final.decls) - 1]:
        var changed = f.copy()
        changed.call_target.link_mode = LinkMode.OWNED_DL_HANDLE
        final.decls[len(final.decls) - 1] = MojoDecl.function_decl(changed^)
    with assert_raises():
        _ = render_mojo_module(final)
    var module = MojoModule("x", "x", "x", LinkMode.EXTERNAL_CALL)
    var callback = ArcPointer(
        MojoType.mojo_function_ptr(
            MojoFunctionPtr(
                ArcPointer(MojoType.builtin_type(BuiltinType(MojoBuiltin.C_INT))),
                List[MojoParam](),
            )
        )
    )
    module.decls.append(
        MojoDecl.alias_decl(AliasDecl("Callback", AliasKind.TYPE_ALIAS, type_value=callback.copy()))
    )
    module.dependencies.imports.append(ModuleImport("std.ffi", [String("c_int")]))
    with assert_raises():
        _ = render_mojo_module(module)
    _ = render_mojo_module(normalize_mojo_module(module))
    module.decls.clear()
    module.decls.append(
        MojoDecl.alias_decl(
            AliasDecl("Callback", AliasKind.CALLBACK_SIGNATURE, type_value=callback.copy())
        )
    )
    if case .mojo_function_ptr(f) = callback[]:
        var changed = f.copy()
        changed.raises_error = True
        callback[] = MojoType.mojo_function_ptr(changed^)
    with assert_raises():
        _ = normalize_mojo_module(module)


def test_verifier_checks_emitted_names_and_actual_dependencies() raises:
    var module = MojoModule("x", "x", "x", LinkMode.EXTERNAL_CALL)
    module.decls.append(MojoDecl.alias_decl(AliasDecl("Name", AliasKind.MACRO_VALUE)))
    module.decls.append(MojoDecl.struct_decl(StructDecl("Name")))
    assert_true("struct Name" in render_mojo_module(module))
    module.decls.append(MojoDecl.struct_decl(StructDecl("Name")))
    with assert_raises():
        _ = normalize_mojo_module(module)
    module.decls.clear()
    var cycle = ArcPointer(MojoType.builtin_type(BuiltinType(MojoBuiltin.C_INT)))
    cycle[] = MojoType.mojo_array(MojoArray(cycle.copy(), 1))
    module.decls.append(
        MojoDecl.alias_decl(AliasDecl("Cycle", AliasKind.TYPE_ALIAS, type_value=cycle.copy()))
    )
    with assert_raises():
        _ = render_mojo_module(module)
    cycle[] = MojoType.builtin_type(BuiltinType(MojoBuiltin.C_INT))


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()

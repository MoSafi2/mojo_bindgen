"""Publication, context isolation, and recovery contracts for recursive IR."""

from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path

import clang.cindex as cx
import pytest

from mojo_bindgen.analysis import AnalysisOrchestrator, build_analysis_context
from mojo_bindgen.analysis.cir.cir_canonicalizer import CIRCanonicalizer
from mojo_bindgen.analysis.cir.validate_ir import IRValidationError, ValidateIRPass
from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass, TypeMappingError
from mojo_bindgen.analysis.mojo.unit_mapping import MapUnitPass
from mojo_bindgen.analysis.type_walk import validate_type_tree
from mojo_bindgen.ir import (
    AtomicType,
    CArray,
    CPointer,
    Decl,
    Function,
    IntKind,
    IntType,
    MojoPointer,
    NamedType,
    Struct,
    StructRef,
    TargetABI,
    Unit,
    UnsupportedType,
)
from mojo_bindgen.parsing.parser import ClangParser
from mojo_bindgen.serde import dumps_cir, dumps_mojo_ir
from tests.bindgen_helpers import DEFAULT_TARGET_QUERIES


def _unit(*decls: Decl, abi: TargetABI | None = None) -> Unit:
    return Unit("test.h", "test", "test", abi or DEFAULT_TARGET_QUERIES._abi, tuple(decls))


def _assert_sealed(value: object) -> None:
    assert not isinstance(value, (list, dict, set))
    if is_dataclass(value) and not isinstance(value, type):
        assert value.__dataclass_params__.frozen
        for field in fields(value):
            _assert_sealed(getattr(value, field.name))
    elif isinstance(value, tuple):
        for item in value:
            _assert_sealed(item)


def test_pipeline_publishes_sealed_ir_and_preserves_every_input(tmp_path: Path) -> None:
    header = tmp_path / "ownership.h"
    header.write_text(
        "struct opaque;\n"
        "struct node { struct node *next; int values[3]; void (*cb)(int); };\n"
        "union item { int x; float y; };\n"
        "struct outer { struct { int x; } inner; union item item; };\n"
        "#define SCALE 0x1.8p2\n"
        "int take(struct node *node, struct opaque *opaque);\n"
    )
    parser = ClangParser(header, library="test", link_name="test")
    unit = parser.run()
    before = dumps_cir(unit)
    analysis = AnalysisOrchestrator()
    artifacts = analysis.analyze_pipeline(unit)
    mapped_before = dumps_mojo_ir(artifacts.policy_light_module)
    assert analysis.finalize(artifacts.policy_light_module) == artifacts.mojo_module
    assert dumps_mojo_ir(artifacts.policy_light_module) == mapped_before
    assert dumps_cir(unit) == before
    assert analysis.analyze(unit) == artifacts.mojo_module
    for result in (
        unit,
        artifacts.normalized_unit,
        artifacts.policy_light_module,
        artifacts.mojo_module,
    ):
        _assert_sealed(result)
    with pytest.raises(FrozenInstanceError):
        setattr(unit, "decls", ())
    # Builder/source state retained by the parser cannot change a published snapshot.
    parser.session.registry._records_by_decl_id.clear()
    parser.compile_args.append("-DUNRELATED=1")
    assert dumps_cir(unit) == before


@pytest.mark.parametrize("has_forward", [False, True])
def test_record_failure_discards_builder_and_restores_prior_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, has_forward: bool
) -> None:
    header = tmp_path / "recovery.h"
    header.write_text("struct node { struct node *next; int value; };\n")
    parser = ClangParser(header, library="test", link_name="test")
    session = parser._build_parser_session()
    lowerer = parser._build_decl_lowerer(session).record_lowerer
    cursor = next(
        c
        for c in session.registry.top_level_cursors_in_order
        if c.kind == cx.CursorKind.STRUCT_DECL
    )
    decl_id = session.registry.decl_id_for_cursor(cursor)
    prior = Struct(decl_id, "node", "node", (), 0, 0, is_complete=False)
    if has_forward:
        session.registry.declare(prior)
    unrelated = Struct("other", "other", "other", (), 4, 4)
    session.registry.publish(unrelated)
    discover = lowerer._field_discovery.discover

    def fail_while_building(cursor: cx.Cursor):
        assert session.registry.get(decl_id) is None
        ref = session.registry.reference(decl_id)
        assert ref is not None and ref.name == "node"
        assert ref.size_bytes == cursor.type.get_size()
        raise RuntimeError("injected discovery failure")

    monkeypatch.setattr(lowerer._field_discovery, "discover", fail_while_building)
    with pytest.raises(RuntimeError, match="injected discovery failure"):
        lowerer.lower_record_definition(cursor)
    assert session.registry.get(decl_id) is None
    assert session.registry.get("other") is unrelated
    assert lowerer.completed_records_since(0) == (0, ())
    assert session.registry.reference(decl_id) == (
        session.registry.make_struct_ref(prior) if has_forward else None
    )
    monkeypatch.setattr(lowerer._field_discovery, "discover", discover)
    completed = lowerer.lower_record_definition(cursor)
    assert completed.is_complete and len(completed.fields) == 2
    assert session.registry.get(decl_id) is completed
    assert lowerer.lower_record_definition(cursor) is completed
    assert prior.fields == () and not prior.is_complete
    _assert_sealed(completed)


def test_structural_cycles_fail_before_analysis_and_mapper_recovers() -> None:
    # Corrupt a frozen payload deliberately; normal construction cannot create this cycle.
    pointer = CPointer(None)
    array = CArray(pointer, 3)
    object.__setattr__(pointer, "pointee", array)
    unit = _unit(Function(name="f", link_name="f", decl_id="f", ret=pointer, params=()))
    for action in (
        lambda: validate_type_tree(pointer),
        lambda: ValidateIRPass().run(unit),
        lambda: build_analysis_context(unit),
        lambda: AnalysisOrchestrator().analyze(unit),
    ):
        with pytest.raises((ValueError, IRValidationError), match="structural CIR type cycle"):
            action()
    mapper = MapTypePass(DEFAULT_TARGET_QUERIES)
    with pytest.raises(ValueError, match="structural CIR type cycle"):
        mapper.run(pointer)
    with pytest.raises(TypeMappingError):
        mapper.run(AtomicType(UnsupportedType("unexposed", "unknown", "unsupported")))
    nominal = StructRef("node", "node", "node", size_bytes=16, align_bytes=8)
    shared = CPointer(nominal)
    valid = CArray(shared, 2)
    first, second = mapper.run(valid), mapper.run(valid)
    assert first == second and first is not second
    # A DAG is allowed even when the exact same child occurs on both owning edges.
    from mojo_bindgen.ir import CFunctionPtr, CParam

    callback = CFunctionPtr(shared, (CParam("p", shared),))
    validate_type_tree(callback)
    assert mapper.run(callback) == mapper.run(callback)


def test_mapping_contexts_remain_bound_to_each_units_char_policy() -> None:
    char = IntType(IntKind.CHAR_S, 1, 1)
    function = Function(name="f", link_name="f", decl_id="f", ret=char, params=())
    x86 = _unit(
        function, abi=replace(DEFAULT_TARGET_QUERIES._abi, target_triple="x86_64-unknown-linux-gnu")
    )
    arm = replace(
        x86, target_abi=replace(x86.target_abi, target_triple="aarch64-unknown-linux-gnu")
    )
    context = build_analysis_context(x86)
    mapping = MapUnitPass(context=context)
    original = mapping.run(x86)
    changed = mapping.run(arm)
    assert original != changed
    assert mapping.run(x86) == original
    assert MapTypePass(TargetQueries(arm.target_abi)).run(CPointer(char)) == MojoPointer(
        NamedType("Int8"), nullable=True
    )
    assert context.unit is x86


def test_canonicalizer_does_not_retain_records_from_previous_units() -> None:
    canonicalizer = CIRCanonicalizer()
    first = _unit(Struct("node", "first", "first", (), 4, 4))
    second = _unit(Struct("node", "second", "second", (), 8, 8))
    first_before = dumps_cir(first)
    assert canonicalizer.canonicalize(first).decls == first.decls
    assert canonicalizer.canonicalize(second).decls == second.decls
    assert canonicalizer.canonicalize(_unit()).decls == ()
    assert dumps_cir(first) == first_before


def test_failed_fact_construction_does_not_partially_update_mapping_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mojo_bindgen.analysis.mojo import struct_mapping

    record = Struct("S", "S", "S", (), 4, 4)
    context = struct_mapping.StructMappingContext(
        record_map={record.decl_id: record}, type_mapper=MapTypePass(DEFAULT_TARGET_QUERIES)
    )
    layouts, storage = context.record_layouts, context.record_storage
    analyze = struct_mapping.analyze_record_storage_facts

    def fail(*args, **kwargs):
        raise RuntimeError("injected fact failure")

    monkeypatch.setattr(struct_mapping, "analyze_record_storage_facts", fail)
    with pytest.raises(RuntimeError, match="injected fact failure"):
        struct_mapping.map_struct(record, context=context)
    assert context.record_layouts is layouts and layouts == {}
    assert context.record_storage is storage and storage == {}
    monkeypatch.setattr(struct_mapping, "analyze_record_storage_facts", analyze)
    assert struct_mapping.map_struct(record, context=context).name == "S"


def test_unit_mapping_failure_keeps_next_run_independent() -> None:
    mapping = MapUnitPass()
    invalid = _unit(
        Function(
            "bad",
            "bad",
            AtomicType(UnsupportedType("unknown", "unknown", "no geometry")),
            (),
            decl_id="bad",
        )
    )
    with pytest.raises(TypeMappingError):
        mapping.run(invalid)
    valid = _unit(Function("ok", "ok", IntType(IntKind.INT, 4, 4), (), decl_id="ok"))
    assert mapping.run(valid) == MapUnitPass().run(valid)


@pytest.mark.parametrize("is_macro", [False, True])
def test_failed_declaration_does_not_claim_an_emitted_constant(is_macro: bool) -> None:
    from mojo_bindgen.analysis.mojo.const_expr_mapping import MapConstExprPass
    from mojo_bindgen.analysis.mojo.decl_mapping import MappingSession, UnitDeclMapper
    from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
    from mojo_bindgen.analysis.mojo.struct_mapping import StructMappingContext
    from mojo_bindgen.ir import AliasDecl, Const, CRefExpr, IntLiteral, MacroDecl

    integer = IntType(IntKind.INT, 4, 4)
    unsupported = AtomicType(UnsupportedType("unknown", "unknown", "no geometry"))
    bad = (
        MacroDecl(
            name="VALUE",
            tokens=("1",),
            kind="object_like_supported",
            expr=IntLiteral(1),
            type=unsupported,
        )
        if is_macro
        else Const(name="VALUE", expr=IntLiteral(1), type=unsupported)
    )
    reference = MacroDecl(
        name="ALIAS",
        tokens=("VALUE",),
        kind="object_like_supported",
        expr=CRefExpr("VALUE"),
        type=integer,
    )
    types = MapTypePass(DEFAULT_TARGET_QUERIES)
    mapper = UnitDeclMapper(
        MappingSession(
            unit=_unit(bad, reference),
            options=MojoEmitOptions(),
            type_mapper=types,
            const_expr_mapper=MapConstExprPass(types),
            struct_context=StructMappingContext({}, types),
        )
    )
    with pytest.raises(TypeMappingError):
        mapper.map_decl(bad)
    (result,) = mapper.map_decl(reference)
    assert isinstance(result, AliasDecl)
    assert result.const_value is None
    assert any("non-emitted" in note.message for note in result.diagnostics)
    # A successful retry publishes the name and makes the same reference usable.
    mapper.map_decl(replace(bad, type=integer))
    (result,) = mapper.map_decl(reference)
    assert isinstance(result, AliasDecl) and result.const_value is not None

"""Analysis pass ordering and per-input ownership boundaries."""
from std.memory import ArcPointer
from ..ir import *
from .cir.validate_ir import ValidateIRPass
from .cir.reachability import SignatureRecordStubPass
from .cir.cir_canonicalizer import CIRCanonicalizer
from .cir.reference_validation import ValidateReferencesPass
from .facts.context import AnalysisContext, build_analysis_context
from .mojo.mojo_emit_options import MojoEmitOptions
from .mojo.unit_mapping import MapUnitPass
from .mojo.record_policies import assign_record_policies
from ..codegen.normalize_mojo_module import normalize_mojo_module


@fieldwise_init
struct AnalysisArtifacts(Copyable, Movable):
    var raw_unit: ArcPointer[Unit]
    var validated_unit: ArcPointer[Unit]
    var normalized_unit: ArcPointer[Unit]
    var context: ArcPointer[AnalysisContext]
    var policy_light_module: MojoModule
    var mojo_module: MojoModule


struct AnalysisOrchestrator(Copyable, Movable):
    var options: MojoEmitOptions

    def __init__(out self, var options: MojoEmitOptions = MojoEmitOptions()):
        self.options = options^

    def normalize_cir(self, unit: Unit) raises -> Unit:
        var validated = ValidateIRPass().run(unit)
        var stubs = SignatureRecordStubPass().run(validated)
        var canonical = CIRCanonicalizer().canonicalize(stubs.unit)
        var revalidated = ValidateIRPass().run(canonical)
        return ValidateReferencesPass().run(revalidated)

    def map_normalized(
        self, unit: ArcPointer[Unit], var context: Optional[ArcPointer[AnalysisContext]] = {}
    ) raises -> MojoModule:
        return MapUnitPass(self.options.copy(), context^).run(unit)

    def finalize(self, module: MojoModule) raises -> MojoModule:
        return normalize_mojo_module(assign_record_policies(module))

    def analyze_pipeline(self, unit: Unit) raises -> AnalysisArtifacts:
        var raw = ArcPointer(unit.copy())
        var validated = ArcPointer(ValidateIRPass().run(unit))
        var stubs = SignatureRecordStubPass().run(validated.ptr()[])
        var canonical = CIRCanonicalizer().canonicalize(stubs.unit)
        var checked = ValidateIRPass().run(canonical)
        var normalized = ArcPointer(ValidateReferencesPass().run(checked))
        var context = ArcPointer(build_analysis_context(normalized))
        var mapped = self.map_normalized(normalized, context.copy())
        var final = self.finalize(mapped)
        return AnalysisArtifacts(raw^, validated^, normalized^, context^, mapped^, final^)

    def analyze(self, unit: Unit) raises -> MojoModule:
        return self.analyze_pipeline(unit).mojo_module.copy()

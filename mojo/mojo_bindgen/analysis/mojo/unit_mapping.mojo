from std.memory import ArcPointer
from ...ir import *
from ..facts.context import AnalysisContext, build_analysis_context
from .type_mapping import MapTypePass
from .const_expr_mapping import MapConstExprPass
from .struct_mapping import StructMappingContext
from .decl_mapping import MappingSession, UnitDeclMapper
from .alias_mapping import map_typedef_alias
from .mojo_emit_options import MojoEmitOptions


struct MapUnitPass(Copyable, Movable):
    var options: MojoEmitOptions
    var context: Optional[ArcPointer[AnalysisContext]]

    def __init__(
        out self,
        var options: MojoEmitOptions = MojoEmitOptions(),
        var context: Optional[ArcPointer[AnalysisContext]] = {},
    ):
        self.options = options^
        self.context = context^

    def run(self, unit: ArcPointer[Unit]) raises -> MojoModule:
        var context: ArcPointer[AnalysisContext]
        if self.context and self.context.value().ptr()[].unit.ptr() == unit.ptr():
            context = self.context.value().copy()
        else:
            context = ArcPointer(build_analysis_context(unit))
        var facts = context.ptr()[].copy()
        var mapper = MapTypePass(facts.target_queries.copy())
        var session = MappingSession(
            unit.copy(),
            self.options.copy(),
            mapper.copy(),
            MapConstExprPass(mapper.copy()),
            StructMappingContext(
                facts.indexes.records_by_decl_id.copy(),
                mapper.copy(),
                facts.record_layouts.copy(),
                facts.record_storage.copy(),
            ),
        )
        var decl_mapper = UnitDeclMapper(session^)
        var result = MojoModule(
            unit.ptr()[].source_header.copy(),
            unit.ptr()[].library.copy(),
            unit.ptr()[].link_name.copy(),
            self.options.linking,
            self.options.library_path_hint.copy(),
        )
        for v in facts.alias_classification.external_type_refs_by_decl_id.values():
            var alias = map_typedef_alias(v.name, v.canonical.ptr()[], mapper)
            if alias:
                result.decls.append(MojoDecl.alias_decl(alias.value().copy()))
        for d in unit.ptr()[].decls:
            result.decls.extend(decl_mapper.map_decl(d))
        return result^

from std.memory import ArcPointer
from ..facts.context import AnalysisContext
from ..facts.c_abi import CABIQueries
from ...ir import *
from ..common import quoted
from .mapping_support import union_note, stub_note, record_name, field_display_name, try_map_type
from .type_mapping import MapTypePass
from ..facts.representation import contains_storage, target_layout, storage_type
from ..facts.type_layout import peel_layout_wrappers


struct MapUnionPass(Copyable, Movable):
    var type_mapper: MapTypePass

    var context: Optional[ArcPointer[AnalysisContext]]

    def __init__(
        out self,
        var type_mapper: MapTypePass,
        var context: Optional[ArcPointer[AnalysisContext]] = {},
    ):
        self.type_mapper = type_mapper^
        self.context = context^

    def _shape(self, t: CType) raises -> Optional[Tuple[Int, Int]]:
        var core = peel_layout_wrappers(t)
        if case .struct_ref(v) = core:
            if self.context and v.decl_id in self.context.value()[].record_storage:
                var queries = CABIQueries(self.context.value().copy())
                if queries.record(v.decl_id).eligible:
                    return self.context.value()[].record_storage[v.decl_id].target_layout
            return {}
        return target_layout(self.type_mapper.run(core), self.type_mapper.queries)

    def run(self, decl: Struct) raises -> AliasDecl:
        if not decl.is_union:
            raise Error("expected union Struct declaration, got non-union " + quoted(decl.decl_id))
        var diagnostics = List[MappingNote]()
        var name = record_name(decl)
        if not decl.is_complete:
            diagnostics.append(stub_note("incomplete union placeholder emitted; layout not mapped"))
            return AliasDecl(
                name^, AliasKind.UNION_LAYOUT, diagnostics=diagnostics^, doc=decl.doc.copy()
            )
        var eligible = decl.size_bytes > 0
        if not eligible:
            diagnostics.append(
                union_note(
                    "union `"
                    + decl.c_name
                    + "` has non-representable byte size "
                    + String(decl.size_bytes)
                    + "; using byte-storage fallback"
                )
            )
        var target_size = 0
        var target_align = 1
        var arms = List[ArcPointer[MojoType]]()
        var arm_names = List[String]()
        for i in range(len(decl.fields)):
            var f = decl.fields[i].copy()
            var field_name = field_display_name(f, i)
            var mapped = try_map_type(
                self.type_mapper,
                f.type.ptr()[],
                "union member `" + field_name + "`",
                "using byte-storage fallback",
            )
            if mapped[1] or not mapped[0]:
                eligible = False
                if mapped[1]:
                    diagnostics.append(union_note(mapped[1].value()))
                continue
            var representation = self.type_mapper.run(peel_layout_wrappers(f.type[]))
            var shape = self._shape(f.type[])
            if not shape or contains_storage(representation):
                eligible = False
            else:
                target_size = max(target_size, shape.value()[0])
                target_align = max(target_align, shape.value()[1])
            var self_reference = False
            match mapped[0].value().ptr()[]:
                case .named_type(v):
                    self_reference = v.name == name
                case _:
                    pass
            if self_reference:
                eligible = False
                diagnostics.append(
                    union_note(
                        "union member `"
                        + field_name
                        + "` mapped to self-referential type `"
                        + name
                        + "`; using byte-storage fallback"
                    )
                )
                continue
            var duplicate = False
            for j in range(len(arms)):
                if equal(arms[j], mapped[0].value()):
                    diagnostics.append(
                        union_note(
                            "union member `"
                            + field_name
                            + "` duplicates mapped type of earlier member `"
                            + arm_names[j]
                            + "`;"
                        )
                    )
                    duplicate = True
                    break
            if not duplicate:
                arms.append(mapped[0].value().copy())
                arm_names.append(field_name^)
        if (
            not len(arms)
            or ((target_size + target_align - 1) // target_align) * target_align != decl.size_bytes
            or target_align != decl.align_bytes
        ):
            eligible = False
        var target: MojoType
        if eligible:
            var args = List[ParametricArg]()
            for arm in arms:
                args.append(ParametricArg.type_arg(TypeArg(arm.copy())))
            target = MojoType.parametric_type(ParametricType(ParametricBase.UNSAFE_UNION, args^))
        else:
            target = storage_type(decl.size_bytes, decl.align_bytes)
            diagnostics.append(
                union_note(
                    "union `"
                    + decl.c_name
                    + "` mapped as aligned opaque storage to preserve size and alignment"
                )
            )
        return AliasDecl(
            name^,
            AliasKind.UNION_LAYOUT,
            type_value=ArcPointer(target^),
            diagnostics=diagnostics^,
            doc=decl.doc.copy(),
        )

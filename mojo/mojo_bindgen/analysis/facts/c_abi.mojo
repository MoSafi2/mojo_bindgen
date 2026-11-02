"""Conservative source-shape checks for Mojo 1.2 memory-only C returns."""
from std.memory import ArcPointer
from ...ir import *
from .context import AnalysisContext
from .record_storage import RecordStorageKind
from .parameter_types import parameter_type
from .type_layout import type_layout, peel_layout_wrappers
from .representation import contains_storage, target_layout
from ..mojo.type_mapping import MapTypePass


@fieldwise_init
struct CABITypeFacts(Copyable, Movable):
    var eligible: Bool
    var contains_array: Bool


struct CABIQueries(Movable):
    var context: ArcPointer[AnalysisContext]
    var records: Dict[String, CABITypeFacts]
    var active: Dict[String, Bool]

    def __init__(out self, var context: ArcPointer[AnalysisContext]):
        self.context = context^
        self.records = Dict[String, CABITypeFacts]()
        self.active = Dict[String, Bool]()

    def type(mut self, t: CType) raises -> CABITypeFacts:
        match t:
            case .type_ref(v):
                return self.type(v.canonical[])
            case .qualified_type(v):
                return self.type(v.unqualified[])
            case .int_type(v):
                if v.int_kind == IntKind.EXT_INT:
                    return CABITypeFacts(False, False)
                return CABITypeFacts(self.scalar(t), False)
            case .float_type(v):
                return CABITypeFacts(v.float_kind != FloatKind.FLOAT16 and self.scalar(t), False)
            case .c_pointer(_) | .c_function_ptr(_):
                return CABITypeFacts(self.scalar(t), False)
            case .void_type(_):
                return CABITypeFacts(True, False)
            case .enum_ref(v):
                return self.type(CType.int_type(v.underlying.copy()))
            case .c_array(v):
                var element = self.type(v.element[])
                return CABITypeFacts(
                    v.array_kind == ArrayKind.fixed
                    and v.size
                    and v.size.value() > 0
                    and element.eligible,
                    True,
                )
            case .struct_ref(v):
                if v.is_union:
                    return CABITypeFacts(False, False)
                return self.record(v.decl_id)
            case .complex_type(v):
                return CABITypeFacts(
                    (
                        self.context[].target_queries.float_format(v.element.float_kind)
                        == FloatFormat.BINARY32
                        or self.context[].target_queries.float_format(v.element.float_kind)
                        == FloatFormat.BINARY64
                    )
                    and self.scalar(t),
                    False,
                )
            case .vector_type(v):
                var eligible = False
                if case .float_type(f) = peel_layout_wrappers(v.element[]):
                    eligible = (
                        f.float_kind == FloatKind.FLOAT
                        and v.count
                        and v.count.value() == 4
                        and v.size_bytes == 16
                        and v.align_bytes
                        and v.align_bytes.value() == 16
                        and self.scalar(t)
                    )
                return CABITypeFacts(eligible, False)
            case .atomic_type(_) | .opaque_record_ref(_) | .unsupported_type(_):
                return CABITypeFacts(False, False)

    def scalar(self, t: CType) raises -> Bool:
        match t:
            case .c_pointer(v):
                return (
                    v.size_bytes == 0
                    or v.size_bytes == self.context[].unit[].target_abi.pointer_size_bytes
                ) and (
                    not v.align_bytes
                    or v.align_bytes.value() == self.context[].unit[].target_abi.pointer_align_bytes
                )
            case .c_function_ptr(v):
                return (
                    v.size_bytes == 0
                    or v.size_bytes == self.context[].unit[].target_abi.pointer_size_bytes
                ) and (
                    not v.align_bytes
                    or v.align_bytes.value() == self.context[].unit[].target_abi.pointer_align_bytes
                )
            case _:
                pass
        var mapper = MapTypePass(self.context[].target_queries.copy())
        var mapped = mapper.run(t)
        var source = type_layout(t)
        var target = target_layout(mapped, mapper.queries)
        return (
            source and target and source.value() == target.value() and not contains_storage(mapped)
        )

    def signature_reason(mut self, function: Function) raises -> Optional[String]:
        if not self.context[].target_queries.supported_c_abi():
            return String("target C ABI has no validated Mojo call profile")
        var ret = peel_layout_wrappers(function.ret[])
        if case .c_array(_) = ret:
            return String("return type is an array")
        if not self.type(function.ret[]).eligible:
            return String("return type has no proven C ABI-compatible Mojo representation")
        for i in range(len(function.params)):
            var t = peel_layout_wrappers(
                parameter_type(function.params[i].type[], self.context[].unit[].target_abi)
            )
            if case .c_array(_) = t:
                return String("parameter " + String(i) + " is an undecayed array")
            if case .void_type(_) = t:
                return String("parameter " + String(i) + " is void")
            if not self.type(t).eligible:
                return String(
                    "parameter " + String(i) + " has no proven C ABI-compatible Mojo representation"
                )
        return {}

    def record(mut self, id: String) raises -> CABITypeFacts:
        if id in self.records:
            return self.records[id].copy()
        if id in self.active or id not in self.context[].record_storage:
            return CABITypeFacts(False, False)
        var context = self.context.copy()
        ref storage = context[].record_storage[id]
        ref layout = storage.layout
        if (
            storage.storage_kind != RecordStorageKind.TYPED
            or storage.flexible_tail
            or layout.is_packed
            or layout.requested_align_bytes
            or len(layout.bitfield_runs)
            or len(layout.padding_spans)
            or layout.size_bytes <= 0
        ):
            return CABITypeFacts(False, False)
        self.active[id] = True
        var result = CABITypeFacts(True, False)
        for field in context[].indexes.records_by_decl_id[id].fields:
            var facts = self.type(field.type[])
            result.eligible = result.eligible and facts.eligible
            result.contains_array = result.contains_array or facts.contains_array
        _ = self.active.pop(id)
        self.records[id] = result.copy()
        return result^

    def extern_type(mut self, t: CType) raises -> Bool:
        var core = peel_layout_wrappers(t)
        match core:
            case .struct_ref(v):
                if not self.record(v.decl_id).eligible:
                    return False
                var context = self.context.copy()
                for field in context[].indexes.records_by_decl_id[v.decl_id].fields:
                    if not self.extern_type(field.type[]):
                        return False
                return True
            case .c_array(v):
                return self.type(core).eligible and self.extern_type(v.element[])
            case .complex_type(_) | .vector_type(_) | .atomic_type(_):
                return False
            case _:
                return self.type(core).eligible

    def memory_return_eligible(mut self, function: Function) raises -> Bool:
        var result = self.type(function.ret[])
        if not result.eligible or not result.contains_array or not self.extern_type(function.ret[]):
            return False
        for param in function.params:
            if not self.extern_type(parameter_type(param.type[], self.context[].unit[].target_abi)):
                return False
        return True

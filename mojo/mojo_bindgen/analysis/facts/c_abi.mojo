"""Conservative source-shape checks for Mojo 1.2 memory-only C returns."""
from std.memory import ArcPointer
from ...ir import *
from .context import AnalysisContext
from .record_storage import RecordStorageKind


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
                return CABITypeFacts(
                    v.int_kind != IntKind.EXT_INT
                    and (
                        v.size_bytes == 1
                        or v.size_bytes == 2
                        or v.size_bytes == 4
                        or v.size_bytes == 8
                        or v.size_bytes == 16
                    ),
                    False,
                )
            case .float_type(v):
                return CABITypeFacts(
                    v.float_kind == FloatKind.FLOAT or v.float_kind == FloatKind.DOUBLE, False
                )
            case .c_pointer(_) | .c_function_ptr(_) | .void_type(_):
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
            case .atomic_type(_) | .opaque_record_ref(_) | .unsupported_type(_) | .complex_type(
                _
            ) | .vector_type(_):
                return CABITypeFacts(False, False)

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

    def memory_return_eligible(mut self, function: Function) raises -> Bool:
        var result = self.type(function.ret[])
        if not result.eligible or not result.contains_array:
            return False
        for param in function.params:
            if not self.type(param.type[]).eligible:
                return False
        return True

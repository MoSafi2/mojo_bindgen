"""Source-to-target C call eligibility for one immutable analysis context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from mojo_bindgen.analysis.facts.context import AnalysisContext
from mojo_bindgen.analysis.facts.parameter_types import parameter_type
from mojo_bindgen.analysis.facts.record_storage import RecordStorageKind
from mojo_bindgen.analysis.facts.representation import contains_storage, target_layout
from mojo_bindgen.analysis.facts.type_layout import peel_layout_wrappers, type_layout
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    AtomicType,
    CArray,
    CFunctionPtr,
    ComplexType,
    CPointer,
    CType,
    EnumRef,
    FloatFormat,
    FloatKind,
    FloatType,
    Function,
    IntKind,
    IntType,
    OpaqueRecordRef,
    QualifiedType,
    StructRef,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)


@dataclass(frozen=True)
class CABITypeFacts:
    eligible: bool
    contains_array: bool = False


class CABIQueries:
    def __init__(self, context: AnalysisContext) -> None:
        self.context = context
        self._records: dict[str, CABITypeFacts] = {}
        self._active: set[str] = set()

    def type(self, t: CType) -> CABITypeFacts:
        match t:
            case TypeRef():
                return self.type(t.canonical)
            case QualifiedType():
                return self.type(t.unqualified)
            case IntType():
                return CABITypeFacts(t.int_kind != IntKind.EXT_INT and self.scalar(t))
            case FloatType():
                return CABITypeFacts(t.float_kind != FloatKind.FLOAT16 and self.scalar(t))
            case CPointer() | CFunctionPtr():
                return CABITypeFacts(self.scalar(t))
            case VoidType():
                return CABITypeFacts(True)
            case EnumRef():
                return self.type(t.underlying)
            case CArray():
                return CABITypeFacts(
                    t.array_kind == "fixed"
                    and t.size is not None
                    and t.size > 0
                    and self.type(t.element).eligible,
                    True,
                )
            case StructRef():
                return CABITypeFacts(False) if t.is_union else self.record(t.decl_id)
            case ComplexType():
                return CABITypeFacts(
                    self.context.target_queries.float_format(t.element.float_kind)
                    in (FloatFormat.BINARY32, FloatFormat.BINARY64)
                    and self.scalar(t)
                )
            case VectorType():
                element = peel_layout_wrappers(t.element)
                return CABITypeFacts(
                    isinstance(element, FloatType)
                    and element.float_kind == FloatKind.FLOAT
                    and t.count == 4
                    and t.size_bytes == t.align_bytes == 16
                    and self.scalar(t)
                )
            case AtomicType() | OpaqueRecordRef() | UnsupportedType():
                return CABITypeFacts(False)

        assert_never(t)

    def scalar(self, t: CType) -> bool:
        abi = self.context.unit.target_abi
        if isinstance(t, CPointer):
            return t.size_bytes in (0, abi.pointer_size_bytes) and t.align_bytes in (
                None,
                abi.pointer_align_bytes,
            )
        if isinstance(t, CFunctionPtr):
            return t.size_bytes in (0, abi.pointer_size_bytes) and t.align_bytes in (
                None,
                abi.pointer_align_bytes,
            )
        mapped = MapTypePass(self.context.target_queries).run(t)
        source = type_layout(t)
        return (
            source is not None
            and source == target_layout(mapped, self.context.target_queries)
            and not contains_storage(mapped)
        )

    def signature_reason(self, function: Function) -> str | None:
        if not self.context.target_queries.supported_c_abi():
            return "target C ABI has no validated Mojo call profile"
        if isinstance(peel_layout_wrappers(function.ret), CArray):
            return "return type is an array"
        if not self.type(function.ret).eligible:
            return "return type has no proven C ABI-compatible Mojo representation"
        for i, param in enumerate(function.params):
            t = peel_layout_wrappers(parameter_type(param.type, self.context.unit.target_abi))
            if isinstance(t, CArray):
                return f"parameter {i} is an undecayed array"
            if isinstance(t, VoidType):
                return f"parameter {i} is void"
            if not self.type(t).eligible:
                return f"parameter {i} has no proven C ABI-compatible Mojo representation"
        return None

    def record(self, key: str) -> CABITypeFacts:
        if key in self._records:
            return self._records[key]
        if key in self._active or key not in self.context.record_storage:
            return CABITypeFacts(False)
        storage = self.context.record_storage[key]
        layout = storage.layout
        if (
            storage.storage_kind != RecordStorageKind.TYPED
            or storage.flexible_tail
            or layout.is_packed
            or layout.requested_align_bytes
            or layout.bitfield_runs
            or layout.padding_spans
            or layout.size_bytes <= 0
        ):
            return CABITypeFacts(False)
        self._active.add(key)
        try:
            fields = tuple(self.type(f.type) for f in self.context.records_by_decl_id[key].fields)
            result = CABITypeFacts(
                all(f.eligible for f in fields), any(f.contains_array for f in fields)
            )
        finally:
            self._active.remove(key)
        self._records[key] = result
        return result

    def extern_type(self, t: CType) -> bool:
        core = peel_layout_wrappers(t)
        if isinstance(core, StructRef):
            return self.record(core.decl_id).eligible and all(
                self.extern_type(f.type)
                for f in self.context.records_by_decl_id[core.decl_id].fields
            )
        if isinstance(core, CArray):
            return self.type(core).eligible and self.extern_type(core.element)
        if isinstance(core, (ComplexType, VectorType, AtomicType)):
            return False
        return self.type(core).eligible

    def memory_return_eligible(self, function: Function) -> bool:
        result = self.type(function.ret)
        return (
            result.eligible
            and self.extern_type(function.ret)
            and result.contains_array
            and all(
                self.extern_type(parameter_type(p.type, self.context.unit.target_abi))
                for p in function.params
            )
        )

"""Reachability pass: materialize incomplete Struct rows for orphan StructRefs.

When the parser emits a :class:`~mojo_bindgen.ir.StructRef` for a tagged record
that never appears as a top-level :class:`~mojo_bindgen.ir.Struct` in the primary
header (e.g. libc types only referenced in signatures), downstream codegen has
no opaque stub to emit. This pass walks all reachable types in a :class:`Unit`,
collects such references, and prepends synthesized incomplete :class:`Struct`
declarations so analysis and rendering can emit Mojo opaque structs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from mojo_bindgen.ir import (
    Array,
    AtomicType,
    CastExpr,
    Const,
    ConstExpr,
    Decl,
    Function,
    FunctionPtr,
    GlobalVar,
    MacroDecl,
    Pointer,
    QualifiedType,
    SizeOfExpr,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Typedef,
    Unit,
    UnaryExpr,
    BinaryExpr,
)


@dataclass(frozen=True)
class ReachabilityOptions:
    """Configure type reachability for orphan :class:`StructRef` collection."""

    traverse_function_ptrs: bool = True
    traverse_const_expr_types: bool = True
    synthesize_union_refs: bool = False


@dataclass(frozen=True)
class ReachabilityMaterializeResult:
    """Output of :class:`ReachabilityMaterializePass`."""

    unit: Unit
    synthesized_structs: tuple[Struct, ...]
    reachable_orphan_decl_ids: frozenset[str]


def _walk_type(
    t: Type,
    out: list[StructRef],
    *,
    traverse_function_ptrs: bool,
) -> None:
    if isinstance(t, StructRef):
        out.append(t)
        return
    if isinstance(t, TypeRef):
        _walk_type(t.canonical, out, traverse_function_ptrs=traverse_function_ptrs)
        return
    if isinstance(t, QualifiedType):
        _walk_type(t.unqualified, out, traverse_function_ptrs=traverse_function_ptrs)
        return
    if isinstance(t, AtomicType):
        _walk_type(t.value_type, out, traverse_function_ptrs=traverse_function_ptrs)
        return
    if isinstance(t, Pointer):
        if t.pointee is not None:
            _walk_type(t.pointee, out, traverse_function_ptrs=traverse_function_ptrs)
        return
    if isinstance(t, Array):
        _walk_type(t.element, out, traverse_function_ptrs=traverse_function_ptrs)
        return
    if isinstance(t, FunctionPtr):
        if traverse_function_ptrs:
            _walk_type(t.ret, out, traverse_function_ptrs=traverse_function_ptrs)
            for p in t.params:
                _walk_type(p, out, traverse_function_ptrs=traverse_function_ptrs)
        return
    # VoidType, IntType, FloatType, EnumRef, OpaqueRecordRef, UnsupportedType,
    # ComplexType, VectorType — no StructRef children.


def _walk_const_expr(
    expr: ConstExpr,
    out: list[StructRef],
    *,
    traverse_function_ptrs: bool,
) -> None:
    if isinstance(expr, CastExpr):
        _walk_type(expr.target, out, traverse_function_ptrs=traverse_function_ptrs)
        _walk_const_expr(
            expr.expr, out, traverse_function_ptrs=traverse_function_ptrs
        )
        return
    if isinstance(expr, SizeOfExpr):
        _walk_type(expr.target, out, traverse_function_ptrs=traverse_function_ptrs)
        return
    if isinstance(expr, UnaryExpr):
        _walk_const_expr(
            expr.operand, out, traverse_function_ptrs=traverse_function_ptrs
        )
        return
    if isinstance(expr, BinaryExpr):
        _walk_const_expr(expr.lhs, out, traverse_function_ptrs=traverse_function_ptrs)
        _walk_const_expr(expr.rhs, out, traverse_function_ptrs=traverse_function_ptrs)


def _collect_from_decl(
    decl: Decl,
    out: list[StructRef],
    *,
    options: ReachabilityOptions,
) -> None:
    traverse_fp = options.traverse_function_ptrs
    if isinstance(decl, Function):
        _walk_type(decl.ret, out, traverse_function_ptrs=traverse_fp)
        for p in decl.params:
            _walk_type(p.type, out, traverse_function_ptrs=traverse_fp)
        return
    if isinstance(decl, Typedef):
        _walk_type(decl.aliased, out, traverse_function_ptrs=traverse_fp)
        _walk_type(decl.canonical, out, traverse_function_ptrs=traverse_fp)
        return
    if isinstance(decl, Struct):
        for f in decl.fields:
            _walk_type(f.type, out, traverse_function_ptrs=traverse_fp)
        return
    if isinstance(decl, GlobalVar):
        _walk_type(decl.type, out, traverse_function_ptrs=traverse_fp)
        if options.traverse_const_expr_types and decl.initializer is not None:
            _walk_const_expr(
                decl.initializer, out, traverse_function_ptrs=traverse_fp
            )
        return
    if isinstance(decl, Const):
        _walk_type(decl.type, out, traverse_function_ptrs=traverse_fp)
        if options.traverse_const_expr_types:
            _walk_const_expr(decl.expr, out, traverse_function_ptrs=traverse_fp)
        return
    if isinstance(decl, MacroDecl):
        if decl.type is not None:
            _walk_type(decl.type, out, traverse_function_ptrs=traverse_fp)
        if options.traverse_const_expr_types and decl.expr is not None:
            _walk_const_expr(decl.expr, out, traverse_function_ptrs=traverse_fp)
        return


def _struct_from_ref(ref: StructRef) -> Struct:
    return Struct(
        decl_id=ref.decl_id,
        name=ref.name,
        c_name=ref.c_name,
        fields=[],
        size_bytes=0,
        align_bytes=1,
        is_union=ref.is_union,
        is_anonymous=ref.is_anonymous,
        is_complete=False,
    )


def materialize_reachable_struct_refs(
    unit: Unit, options: ReachabilityOptions | None = None
) -> Unit:
    """Return a new Unit with synthesized incomplete Structs prepended."""
    return ReachabilityMaterializePass().run(unit, options).unit


class ReachabilityMaterializePass:
    """Insert incomplete :class:`Struct` declarations for orphan :class:`StructRef` uses."""

    def run(
        self,
        unit: Unit,
        options: ReachabilityOptions | None = None,
    ) -> ReachabilityMaterializeResult:
        opts = options or ReachabilityOptions()
        collected: list[StructRef] = []
        for decl in unit.decls:
            _collect_from_decl(decl, collected, options=opts)

        existing: set[str] = {
            d.decl_id for d in unit.decls if isinstance(d, Struct)
        }

        # Unique by decl_id; first occurrence wins for ordering among duplicates.
        seen_ids: set[str] = set()
        orphans: list[StructRef] = []
        for ref in collected:
            if ref.decl_id in existing or ref.decl_id in seen_ids:
                continue
            if ref.is_union and not opts.synthesize_union_refs:
                continue
            seen_ids.add(ref.decl_id)
            orphans.append(ref)

        orphans_sorted = sorted(orphans, key=lambda r: r.decl_id)
        synthesized = tuple(_struct_from_ref(ref) for ref in orphans_sorted)
        orphan_ids = frozenset(s.decl_id for s in synthesized)

        if not synthesized:
            return ReachabilityMaterializeResult(
                unit=unit,
                synthesized_structs=(),
                reachable_orphan_decl_ids=frozenset(),
            )

        new_decls: list[Decl] = list(synthesized)
        new_decls.extend(unit.decls)
        new_unit = replace(unit, decls=new_decls)
        return ReachabilityMaterializeResult(
            unit=new_unit,
            synthesized_structs=synthesized,
            reachable_orphan_decl_ids=orphan_ids,
        )

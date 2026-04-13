"""Value-embedding struct dependency ordering for code generation.

These helpers compute an emission order for structs that embed other structs
by value, so referenced layouts appear before the records that depend on them.
"""

from __future__ import annotations

from collections import defaultdict, deque

from mojo_bindgen.ir import Array, EnumRef, Struct, StructRef, Type, TypeRef
from mojo_bindgen.codegen.lowering import mojo_ident


def struct_dependency_edges(s: Struct) -> list[tuple[str, str]]:
    """Return (successor, predecessor) pairs: `succ` depends on `pred` (emit `pred` first).

    Only **by-value** struct references create ordering edges. Pointer and function-pointer
    fields do not (C allows pointers to incomplete types); nested struct layout is still
    captured via ``Array``/``StructRef`` for value-embedded arrays of structs.
    """
    me = mojo_ident(s.name.strip() or s.c_name.strip())
    edges: list[tuple[str, str]] = []

    def walk(ty: Type) -> None:
        """Collect by-value struct dependencies reachable from ``ty``."""
        if isinstance(ty, TypeRef):
            walk(ty.canonical)
            return
        if isinstance(ty, EnumRef):
            return
        if isinstance(ty, StructRef):
            if ty.is_union:
                return
            pred = mojo_ident(ty.name.strip())
            if pred != me:
                edges.append((me, pred))
            return
        if isinstance(ty, Array):
            walk(ty.element)

    for f in s.fields:
        walk(f.type)
    return edges


def toposort_structs(structs: list[Struct]) -> list[Struct]:
    """Return structs in an order suitable for emission.

    Value-embedded :class:`~mojo_bindgen.ir.StructRef` dependencies are emitted
    before the records that use them. Cycles fall back to the original input
    order once the acyclic portion of the graph is exhausted.
    """
    if not structs:
        return []

    def name_of(s: Struct) -> str:
        """Return the sanitized emitted name for ``s``."""
        return mojo_ident(s.name.strip() or s.c_name.strip())

    names = [name_of(s) for s in structs]
    known = set(names)
    name_to_struct = {name_of(s): s for s in structs}

    # graph[pred] = successors that must appear after pred
    graph: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {n: 0 for n in names}

    for s in structs:
        succ = name_of(s)
        for succ2, pred in struct_dependency_edges(s):
            if succ2 != succ:
                continue
            if pred in known and pred != succ:
                if succ not in graph[pred]:
                    graph[pred].add(succ)
                    indegree[succ] += 1

    q = deque(sorted([n for n in names if indegree[n] == 0], key=lambda x: names.index(x)))
    order: list[str] = []
    while q:
        n = q.popleft()
        order.append(n)
        for succ in graph.get(n, ()):
            indegree[succ] -= 1
            if indegree[succ] == 0:
                q.append(succ)

    for n in names:
        if n not in order:
            order.append(n)

    return [name_to_struct[n] for n in order]

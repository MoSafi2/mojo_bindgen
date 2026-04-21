"""Union-specific Mojo analysis."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.model import AnalyzedUnion
from mojo_bindgen.codegen.mojo_emit_options import FFIScalarStyle
from mojo_bindgen.codegen.mojo_mapper import FFIOriginStyle, TypeMapper, mojo_ident, peel_wrappers
from mojo_bindgen.ir import Struct, Unit, UnsupportedType


@dataclass(frozen=True)
class UnionFacts:
    unions: tuple[AnalyzedUnion, ...]
    union_alias_names: frozenset[str]
    unsafe_union_names: frozenset[str]


class AnalyzeUnionLoweringPass:
    """Analyze union lowering independently of other declaration kinds."""

    def run(
        self,
        unit: Unit,
        *,
        ffi_origin: FFIOriginStyle,
        ffi_scalar_style: FFIScalarStyle = "std_ffi_aliases",
    ) -> UnionFacts:
        unions: list[AnalyzedUnion] = []
        union_alias_names: set[str] = set()
        unsafe_union_names: set[str] = set()
        mapper = TypeMapper(
            ffi_origin=ffi_origin,
            union_alias_names=frozenset(),
            unsafe_union_names=frozenset(),
            typedef_mojo_names=frozenset(),
            callback_signature_names=frozenset(),
            ffi_scalar_style=ffi_scalar_style,
        )
        for decl in unit.decls:
            if not isinstance(decl, Struct) or not decl.is_union or not decl.is_complete:
                continue
            mojo_name = mojo_ident(decl.name.strip() or decl.c_name.strip())
            union_alias_names.add(mojo_name)
            mapped_members: list[str] = []
            supported = True
            for field in decl.fields:
                if isinstance(peel_wrappers(field.type), UnsupportedType):
                    supported = False
                    break
                mapped = mapper.canonical(field.type)
                if mapped == mojo_name or mapped in mapped_members:
                    supported = False
                    break
                mapped_members.append(mapped)
            if supported:
                unsafe_union_names.add(mojo_name)
                comptime_expr_text = f"UnsafeUnion[{', '.join(mapped_members)}]"
                comment_lines = (
                    (
                        f"# -- C union `{decl.c_name}` - comptime `{mojo_name}` = UnsafeUnion[...].",
                        f"# C size={decl.size_bytes} bytes, align={decl.align_bytes}.",
                        "# Members (reference only):",
                    )
                    + tuple(
                        f"#   {field.name if field.name else '(anonymous)'}: {mapper.canonical(field.type)}"
                        for field in decl.fields
                    )
                    + ("",)
                )
                unions.append(
                    AnalyzedUnion(
                        decl=decl,
                        mojo_name=mojo_name,
                        kind="unsafe_union",
                        comptime_expr_text=comptime_expr_text,
                        comment_lines=comment_lines,
                        unsafe_member_types=tuple(mapped_members),
                    )
                )
            else:
                comptime_expr_text = f"InlineArray[UInt8, {decl.size_bytes}]"
                comment_lines = (
                    (
                        f"# -- C union `{decl.c_name}` lowered as InlineArray[UInt8, {decl.size_bytes}] to preserve layout.",
                        "# It could not be represented as UnsafeUnion[...] with distinct supported member types.",
                        f"# C size={decl.size_bytes} bytes, align={decl.align_bytes}.",
                        "# Members (reference only):",
                    )
                    + tuple(
                        f"#   {field.name if field.name else '(anonymous)'}: {mapper.canonical(field.type)}"
                        for field in decl.fields
                    )
                    + ("",)
                )
                unions.append(
                    AnalyzedUnion(
                        decl=decl,
                        mojo_name=mojo_name,
                        kind="inline_array",
                        comptime_expr_text=comptime_expr_text,
                        comment_lines=comment_lines,
                    )
                )
        return UnionFacts(
            unions=tuple(unions),
            union_alias_names=frozenset(union_alias_names),
            unsafe_union_names=frozenset(unsafe_union_names),
        )


__all__ = ["AnalyzeUnionLoweringPass", "UnionFacts"]

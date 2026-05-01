"""Late record-policy assignment on lowered MojoIR."""

from __future__ import annotations

from dataclasses import dataclass, replace

from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    ArrayType,
    BitfieldGroupMember,
    BuiltinType,
    FunctionType,
    MojoBuiltin,
    MojoDecl,
    MojoModule,
    MojoPassability,
    MojoType,
    NamedType,
    OpaqueStorageMember,
    PaddingMember,
    ParametricBase,
    ParametricType,
    PointerType,
    StoredMember,
    StructDecl,
    StructKind,
    StructMember,
    StructTraits,
)


class AssignRecordPoliciesError(ValueError):
    """Raised when late record policy derivation cannot complete safely."""


_TRIVIAL_BUILTINS = frozenset(
    builtin for builtin in MojoBuiltin if builtin != MojoBuiltin.UNSUPPORTED
)

_TRIVIAL_NAMED_TYPES = frozenset(
    {
        "Bool",
        "Byte",
        "Float16",
        "Float32",
        "Float64",
        "Int",
        "Int8",
        "Int16",
        "Int32",
        "Int64",
        "Int128",
        "UInt",
        "UInt8",
        "UInt16",
        "UInt32",
        "UInt64",
        "UInt128",
    }
)


@dataclass
class PolicyInferencePass:
    """Infer final Mojo record passability, traits, and fieldwise-init policy."""

    def run(self, module: MojoModule) -> MojoModule:
        self._structs = {decl.name: decl for decl in module.decls if isinstance(decl, StructDecl)}
        self._aliases = {decl.name: decl for decl in module.decls if isinstance(decl, AliasDecl)}
        self._cache: dict[str, MojoPassability] = {}
        self._computing: set[str] = set()

        return replace(
            module,
            decls=[self._assign_decl_policies(decl) for decl in module.decls],
        )

    def _assign_decl_policies(self, decl: MojoDecl) -> MojoDecl:
        if not isinstance(decl, StructDecl):
            return decl
        if decl.kind == StructKind.ENUM:
            return replace(
                decl,
                passability=MojoPassability.REGISTER_PASSABLE,
                traits=[
                    StructTraits.COPYABLE,
                    StructTraits.MOVABLE,
                    StructTraits.REGISTER_PASSABLE,
                ],
                fieldwise_init=True,
            )
        passability = self._record_passability(decl.name)
        if self._has_representable_atomic_storage(decl):
            return replace(
                decl,
                passability=passability,
                traits=[],
                fieldwise_init=False,
            )

        return replace(
            decl,
            passability=passability,
            traits=self._traits_for_passability(passability),
            fieldwise_init=self._is_fieldwise_init_eligible(decl),
        )

    def _is_fieldwise_init_eligible(self, decl: StructDecl) -> bool:
        if decl.kind != StructKind.PLAIN:
            return False
        if self._has_opaque_storage(decl):
            return False
        if self._has_representable_atomic_storage(decl):
            return False
        if self._is_pure_bitfield(decl):
            return False
        return True

    def _record_passability(self, name: str) -> MojoPassability:
        if name in self._cache:
            return self._cache[name]
        if name in self._computing:
            return MojoPassability.MEMORY_ONLY

        decl = self._structs.get(name)
        if decl is None or decl.kind != StructKind.PLAIN:
            self._cache[name] = MojoPassability.MEMORY_ONLY
            return MojoPassability.MEMORY_ONLY
        if self._has_representable_atomic_storage(decl):
            self._cache[name] = MojoPassability.MEMORY_ONLY
            return MojoPassability.MEMORY_ONLY

        self._computing.add(name)
        try:
            member_passabilities = [self._member_passability(member) for member in decl.members]
        finally:
            self._computing.remove(name)

        if all(
            passability == MojoPassability.TRIVIAL_REGISTER_PASSABLE
            for passability in member_passabilities
        ):
            result = MojoPassability.TRIVIAL_REGISTER_PASSABLE
        elif all(
            passability
            in (
                MojoPassability.REGISTER_PASSABLE,
                MojoPassability.TRIVIAL_REGISTER_PASSABLE,
            )
            for passability in member_passabilities
        ):
            result = MojoPassability.REGISTER_PASSABLE
        else:
            result = MojoPassability.MEMORY_ONLY

        self._cache[name] = result
        return result

    def _member_passability(self, member: StructMember) -> MojoPassability:
        if isinstance(member, StoredMember):
            return self._type_passability(member.type)
        if isinstance(member, BitfieldGroupMember):
            return self._type_passability(member.storage_type)
        if isinstance(member, PaddingMember):
            return MojoPassability.TRIVIAL_REGISTER_PASSABLE
        if isinstance(member, OpaqueStorageMember):
            return MojoPassability.MEMORY_ONLY
        raise AssignRecordPoliciesError(
            f"unsupported StructMember for passability: {type(member).__name__!r}"
        )

    def _type_passability(self, t: MojoType) -> MojoPassability:
        if isinstance(t, BuiltinType):
            if t.name in _TRIVIAL_BUILTINS:
                return MojoPassability.TRIVIAL_REGISTER_PASSABLE
            return MojoPassability.MEMORY_ONLY
        if isinstance(t, FunctionType):
            return MojoPassability.TRIVIAL_REGISTER_PASSABLE
        if isinstance(t, PointerType):
            if t.nullable:
                return MojoPassability.REGISTER_PASSABLE
            return MojoPassability.TRIVIAL_REGISTER_PASSABLE
        if isinstance(t, ArrayType):
            return MojoPassability.MEMORY_ONLY
        if isinstance(t, ParametricType):
            if t.base in (ParametricBase.SIMD, ParametricBase.COMPLEX_SIMD):
                return MojoPassability.TRIVIAL_REGISTER_PASSABLE
            return MojoPassability.MEMORY_ONLY
        if isinstance(t, NamedType):
            if t.name in _TRIVIAL_NAMED_TYPES:
                return MojoPassability.TRIVIAL_REGISTER_PASSABLE

            struct_decl = self._structs.get(t.name)
            if struct_decl is not None:
                return self._record_passability(struct_decl.name)

            alias_decl = self._aliases.get(t.name)
            if alias_decl is None:
                return MojoPassability.MEMORY_ONLY
            if alias_decl.kind == AliasKind.CALLBACK_SIGNATURE:
                return MojoPassability.TRIVIAL_REGISTER_PASSABLE
            if alias_decl.kind == AliasKind.UNION_LAYOUT:
                return MojoPassability.MEMORY_ONLY
            if alias_decl.kind != AliasKind.TYPE_ALIAS or alias_decl.type_value is None:
                return MojoPassability.MEMORY_ONLY
            return self._type_passability(alias_decl.type_value)
        raise AssignRecordPoliciesError(
            f"unsupported MojoType for passability: {type(t).__name__!r}"
        )

    @staticmethod
    def _traits_for_passability(passability: MojoPassability) -> list[StructTraits]:
        if passability == MojoPassability.TRIVIAL_REGISTER_PASSABLE:
            return [StructTraits.TRIVIAL_REGISTER_PASSABLE]
        if passability == MojoPassability.REGISTER_PASSABLE:
            return [StructTraits.REGISTER_PASSABLE]
        return [StructTraits.COPYABLE, StructTraits.MOVABLE]

    @staticmethod
    def _has_opaque_storage(decl: StructDecl) -> bool:
        return any(isinstance(member, OpaqueStorageMember) for member in decl.members)

    @staticmethod
    def _has_representable_atomic_storage(decl: StructDecl) -> bool:
        for member in decl.members:
            if isinstance(member, StoredMember) and isinstance(member.type, ParametricType):
                if member.type.base == ParametricBase.ATOMIC:
                    return True
        return False

    @staticmethod
    def _is_pure_bitfield(decl: StructDecl) -> bool:
        return bool(decl.members) and all(
            isinstance(member, BitfieldGroupMember) for member in decl.members
        )


def assign_record_policies(module: MojoModule) -> MojoModule:
    """Assign final record policy bits to a fully lowered ``MojoModule``."""

    return PolicyInferencePass().run(module)


AssignRecordPoliciesPass = PolicyInferencePass


__all__ = [
    "AssignRecordPoliciesError",
    "AssignRecordPoliciesPass",
    "PolicyInferencePass",
    "assign_record_policies",
]

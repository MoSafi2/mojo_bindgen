"""Late record-policy assignment on lowered MojoIR."""

from __future__ import annotations

from dataclasses import dataclass, replace

from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    ArrayType,
    BitfieldGroupMember,
    BuiltinType,
    CallbackType,
    FunctionType,
    MojoDecl,
    MojoModule,
    MojoType,
    NamedType,
    OpaqueStorageMember,
    ParametricBase,
    ParametricType,
    PointerType,
    StoredMember,
    StructDecl,
    StructKind,
    StructTraits,
)


class AssignRecordPoliciesError(ValueError):
    """Raised when late record policy derivation cannot complete safely."""


@dataclass
class AssignRecordPoliciesPass:
    """Derive final record traits and fieldwise-init policy from lowered MojoIR."""

    def run(self, module: MojoModule) -> MojoModule:
        self._structs = {decl.name: decl for decl in module.decls if isinstance(decl, StructDecl)}
        self._aliases = {decl.name: decl for decl in module.decls if isinstance(decl, AliasDecl)}
        self._cache: dict[str, bool] = {}
        self._computing: set[str] = set()

        return replace(
            module,
            decls=[self._assign_decl_policies(decl) for decl in module.decls],
        )

    def _assign_decl_policies(self, decl: MojoDecl) -> MojoDecl:
        if not isinstance(decl, StructDecl):
            return decl
        if self._has_representable_atomic_storage(decl):
            return replace(decl, traits=[], fieldwise_init=False)

        traits = [StructTraits.COPYABLE, StructTraits.MOVABLE]
        if self._is_register_passable_struct(decl.name):
            traits.append(StructTraits.REGISTER_PASSABLE)
        return replace(
            decl,
            traits=traits,
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

    def _is_register_passable_struct(self, name: str) -> bool:
        if name in self._cache:
            return self._cache[name]
        if name in self._computing:
            return False

        decl = self._structs.get(name)
        if decl is None or decl.kind != StructKind.PLAIN:
            self._cache[name] = False
            return False
        if self._has_opaque_storage(decl):
            self._cache[name] = False
            return False
        if self._has_representable_atomic_storage(decl):
            self._cache[name] = False
            return False
        if any(not isinstance(member, StoredMember) for member in decl.members):
            self._cache[name] = False
            return False

        self._computing.add(name)
        try:
            is_passable = all(
                self._type_is_register_passable(member.type)  # pyright: ignore[reportAttributeAccessIssue]
                for member in decl.members
            )
        finally:
            self._computing.remove(name)

        self._cache[name] = is_passable
        return is_passable

    def _type_is_register_passable(self, t: MojoType) -> bool:
        if isinstance(t, (BuiltinType, CallbackType, FunctionType)):
            return True
        if isinstance(t, PointerType):
            if t.pointee is None:
                return True
            return self._type_is_register_passable(t.pointee)
        if isinstance(t, ArrayType):
            return False
        if isinstance(t, ParametricType):
            if t.base in (ParametricBase.SIMD, ParametricBase.COMPLEX_SIMD):
                return True
            return False
        if isinstance(t, NamedType):
            struct_decl = self._structs.get(t.name)
            if struct_decl is not None:
                return self._is_register_passable_struct(struct_decl.name)

            alias_decl = self._aliases.get(t.name)
            if alias_decl is None:
                return False
            if alias_decl.kind == AliasKind.CALLBACK_SIGNATURE:
                return True
            if alias_decl.kind == AliasKind.UNION_LAYOUT:
                return False
            if alias_decl.kind != AliasKind.TYPE_ALIAS or alias_decl.type_value is None:
                return False
            return self._type_is_register_passable(alias_decl.type_value)
        raise AssignRecordPoliciesError(
            f"unsupported MojoType for passability: {type(t).__name__!r}"
        )

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

    return AssignRecordPoliciesPass().run(module)


__all__ = [
    "AssignRecordPoliciesError",
    "AssignRecordPoliciesPass",
    "assign_record_policies",
]

"""Late record-policy assignment on mapped MojoIR."""

from __future__ import annotations

from dataclasses import dataclass, replace

from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    Array,
    BitfieldGroupMember,
    BuiltinType,
    FunctionPtr,
    MojoBuiltin,
    MojoDecl,
    MojoModule,
    MojoPassability,
    NamedType,
    OpaqueStorageMember,
    PaddingMember,
    ParametricBase,
    ParametricType,
    Pointer,
    StoredMember,
    StructDecl,
    StructKind,
    StructMember,
    StructTraits,
    Type,
    TypeArg,
)


class AssignRecordPoliciesError(ValueError):
    """Raised when late record policy derivation cannot complete safely."""


@dataclass(frozen=True)
class TransferTraits:
    """Copy and move capability inferred separately from register passability."""

    copyable: bool
    movable: bool


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
        self._passability_cache: dict[str, MojoPassability] = {}
        self._passability_computing: set[str] = set()
        self._transfer_cache: dict[str, TransferTraits] = {}
        self._transfer_computing: set[str] = set()

        return replace(
            module,
            decls=[self._assign_decl_policies(decl) for decl in module.decls],
        )

    def _assign_decl_policies(self, decl: MojoDecl) -> MojoDecl:
        if not isinstance(decl, StructDecl):
            return decl
        passability = self._record_passability(decl.name)
        transfer_traits = self._record_transfer_traits(decl.name)
        if self._has_representable_atomic_storage(decl) or decl.flexible_tail is not None:
            return replace(
                decl,
                passability=passability,
                traits=[],
                fieldwise_init=False,
            )

        return replace(
            decl,
            passability=passability,
            traits=self._traits_for_decl(decl, passability, transfer_traits),
            fieldwise_init=self._is_fieldwise_init_eligible(decl),
        )

    def _is_fieldwise_init_eligible(self, decl: StructDecl) -> bool:
        if decl.kind != StructKind.PLAIN:
            return False
        if decl.flexible_tail is not None:
            return False
        if self._has_opaque_storage(decl):
            return False
        if self._has_representable_atomic_storage(decl):
            return False
        if self._is_pure_bitfield(decl):
            return False
        return True

    def _record_passability(self, name: str) -> MojoPassability:
        if name in self._passability_cache:
            return self._passability_cache[name]
        if name in self._passability_computing:
            return MojoPassability.MEMORY_ONLY

        decl = self._structs.get(name)
        if decl is None or decl.kind != StructKind.PLAIN:
            self._passability_cache[name] = MojoPassability.MEMORY_ONLY
            return MojoPassability.MEMORY_ONLY
        if decl.flexible_tail is not None:
            self._passability_cache[name] = MojoPassability.MEMORY_ONLY
            return MojoPassability.MEMORY_ONLY
        if self._has_representable_atomic_storage(decl):
            self._passability_cache[name] = MojoPassability.MEMORY_ONLY
            return MojoPassability.MEMORY_ONLY

        self._passability_computing.add(name)
        try:
            member_passabilities = [self._member_passability(member) for member in decl.members]
        finally:
            self._passability_computing.remove(name)

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

        self._passability_cache[name] = result
        return result

    def _record_transfer_traits(self, name: str) -> TransferTraits:
        if name in self._transfer_cache:
            return self._transfer_cache[name]
        if name in self._transfer_computing:
            return TransferTraits(copyable=True, movable=True)

        decl = self._structs.get(name)
        if decl is None:
            return TransferTraits(copyable=False, movable=False)
        if decl.flexible_tail is not None or self._has_representable_atomic_storage(decl):
            result = TransferTraits(copyable=False, movable=False)
            self._transfer_cache[name] = result
            return result
        if decl.kind != StructKind.PLAIN:
            result = TransferTraits(copyable=True, movable=True)
            self._transfer_cache[name] = result
            return result

        if self._has_opaque_storage(decl):
            # Experimental default: byte-backed fallback storage stays movable/copyable
            # so generated wrappers remain usable while opaque record semantics are still
            # being validated across real headers.
            result = TransferTraits(copyable=True, movable=True)
            self._transfer_cache[name] = result
            return result

        self._transfer_computing.add(name)
        try:
            member_traits = [self._member_transfer_traits(member) for member in decl.members]
        finally:
            self._transfer_computing.remove(name)

        result = TransferTraits(
            copyable=all(traits.copyable for traits in member_traits),
            movable=all(traits.movable for traits in member_traits),
        )
        self._transfer_cache[name] = result
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

    def _member_transfer_traits(self, member: StructMember) -> TransferTraits:
        if isinstance(member, StoredMember):
            return self._type_transfer_traits(member.type)
        if isinstance(member, BitfieldGroupMember):
            return self._type_transfer_traits(member.storage_type)
        if isinstance(member, PaddingMember):
            return TransferTraits(copyable=True, movable=True)
        if isinstance(member, OpaqueStorageMember):
            return TransferTraits(copyable=True, movable=True)
        raise AssignRecordPoliciesError(
            f"unsupported StructMember for transfer traits: {type(member).__name__!r}"
        )

    def _type_passability(self, t: Type) -> MojoPassability:
        if isinstance(t, BuiltinType):
            if t.name in _TRIVIAL_BUILTINS:
                return MojoPassability.TRIVIAL_REGISTER_PASSABLE
            return MojoPassability.MEMORY_ONLY
        if isinstance(t, FunctionPtr):
            return MojoPassability.TRIVIAL_REGISTER_PASSABLE
        if isinstance(t, Pointer):
            if t.nullable:
                return MojoPassability.REGISTER_PASSABLE
            return MojoPassability.TRIVIAL_REGISTER_PASSABLE
        if isinstance(t, Array):
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
        raise AssignRecordPoliciesError(f"unsupported Type for passability: {type(t).__name__!r}")

    @staticmethod
    def _passability_traits(passability: MojoPassability) -> list[StructTraits]:
        if passability == MojoPassability.TRIVIAL_REGISTER_PASSABLE:
            return [StructTraits.TRIVIAL_REGISTER_PASSABLE]
        if passability == MojoPassability.REGISTER_PASSABLE:
            return [StructTraits.REGISTER_PASSABLE]
        return []

    def _type_transfer_traits(self, t: Type) -> TransferTraits:
        if isinstance(t, BuiltinType):
            supported = t.name in _TRIVIAL_BUILTINS
            return TransferTraits(copyable=supported, movable=supported)
        if isinstance(t, FunctionPtr):
            return TransferTraits(copyable=True, movable=True)
        if isinstance(t, Pointer):
            return TransferTraits(copyable=True, movable=True)
        if isinstance(t, Array):
            if t.array_kind != "fixed" or t.size is None:
                return TransferTraits(copyable=False, movable=False)
            return self._type_transfer_traits(t.element)
        if isinstance(t, ParametricType):
            if t.base == ParametricBase.ATOMIC:
                return TransferTraits(copyable=False, movable=False)
            if t.base in (ParametricBase.SIMD, ParametricBase.COMPLEX_SIMD):
                return TransferTraits(copyable=True, movable=True)
            if t.base == ParametricBase.UNSAFE_UNION:
                arg_traits = [self._transfer_traits_for_parametric_arg(arg) for arg in t.args]
                return TransferTraits(
                    copyable=all(traits.copyable for traits in arg_traits),
                    movable=all(traits.movable for traits in arg_traits),
                )
            return TransferTraits(copyable=False, movable=False)
        if isinstance(t, NamedType):
            if t.name in _TRIVIAL_NAMED_TYPES:
                return TransferTraits(copyable=True, movable=True)

            struct_decl = self._structs.get(t.name)
            if struct_decl is not None:
                return self._record_transfer_traits(struct_decl.name)

            alias_decl = self._aliases.get(t.name)
            if alias_decl is None:
                return TransferTraits(copyable=False, movable=False)
            if alias_decl.kind == AliasKind.CALLBACK_SIGNATURE:
                return TransferTraits(copyable=True, movable=True)
            if alias_decl.kind in (AliasKind.TYPE_ALIAS, AliasKind.UNION_LAYOUT):
                if alias_decl.type_value is None:
                    return TransferTraits(copyable=False, movable=False)
                return self._type_transfer_traits(alias_decl.type_value)
            return TransferTraits(copyable=False, movable=False)
        raise AssignRecordPoliciesError(
            f"unsupported Type for transfer traits: {type(t).__name__!r}"
        )

    def _transfer_traits_for_parametric_arg(self, arg) -> TransferTraits:
        if isinstance(arg, TypeArg):
            return self._type_transfer_traits(arg.type)
        return TransferTraits(copyable=True, movable=True)

    def _traits_for_decl(
        self,
        decl: StructDecl,
        passability: MojoPassability,
        transfer_traits: TransferTraits,
    ) -> list[StructTraits]:
        traits = list(self._passability_traits(passability))
        if decl.flexible_tail is None and not self._has_representable_atomic_storage(decl):
            if transfer_traits.copyable:
                traits.append(StructTraits.COPYABLE)
            if transfer_traits.movable:
                traits.append(StructTraits.MOVABLE)
        return traits

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
    """Assign final record policy bits to a fully mapped ``MojoModule``."""

    return PolicyInferencePass().run(module)


AssignRecordPoliciesPass = PolicyInferencePass


__all__ = [
    "AssignRecordPoliciesError",
    "AssignRecordPoliciesPass",
    "PolicyInferencePass",
    "assign_record_policies",
]

"""Queries over the canonical target facts attached to a CIR unit."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.ir import TargetABI


@dataclass(frozen=True)
class TargetQueries:
    """Shared target queries; passes consume answers rather than target fields."""

    _abi: TargetABI

    def default_char_is_unsigned(self) -> bool | None:
        """Return ABI-default char signedness on supported targets, if known.

        Explicit Clang signedness overrides are recorded separately in IntKind.
        """
        triple = self._abi.target_triple
        if triple is None:
            return None
        return "linux" in triple and triple.startswith(("aarch64", "arm", "thumb"))

"""Queries over the canonical target facts attached to a CIR unit."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.ir import (
    ByteOrder,
    FloatFormat,
    FloatKind,
    FloatType,
    MojoBuiltin,
    TargetABI,
)


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

    def float_format(self, kind: FloatKind) -> FloatFormat:
        for item in self._abi.float_abi:
            if item.kind == kind:
                return item.format
        return {
            FloatKind.FLOAT16: FloatFormat.BINARY16,
            FloatKind.FLOAT: FloatFormat.BINARY32,
            FloatKind.DOUBLE: FloatFormat.BINARY64,
            FloatKind.FLOAT128: FloatFormat.BINARY128,
        }.get(kind, FloatFormat.UNKNOWN)

    def float_compatible(self, v: FloatType) -> bool:
        width = {FloatFormat.BINARY16: 2, FloatFormat.BINARY32: 4, FloatFormat.BINARY64: 8}.get(
            self.float_format(v.float_kind)
        )
        return (
            width is not None
            and v.size_bytes == width
            and v.align_bytes == min(width, self._abi.pointer_align_bytes)
        )

    def supported_c_abi(self) -> bool:
        triple = self._abi.target_triple or ""
        return (
            triple.startswith("x86_64-")
            and "linux" in triple
            and self._abi.pointer_size_bytes == self._abi.pointer_align_bytes == 8
            and self._abi.byte_order == ByteOrder.LITTLE
        )

    def builtin_layout(self, name: MojoBuiltin) -> tuple[int, int] | None:
        widths = {
            MojoBuiltin.BOOL: 1,
            MojoBuiltin.UINT8: 1,
            MojoBuiltin.INT8: 1,
            MojoBuiltin.C_CHAR: 1,
            MojoBuiltin.C_UCHAR: 1,
            MojoBuiltin.FLOAT16: 2,
            MojoBuiltin.C_SHORT: 2,
            MojoBuiltin.C_USHORT: 2,
            MojoBuiltin.C_INT: 4,
            MojoBuiltin.C_UINT: 4,
            MojoBuiltin.C_FLOAT: 4,
            MojoBuiltin.C_DOUBLE: 8,
            MojoBuiltin.C_LONG_LONG: 8,
            MojoBuiltin.C_ULONG_LONG: 8,
        }
        if name in (MojoBuiltin.INT128, MojoBuiltin.UINT128):
            return 16, 16
        if name in (MojoBuiltin.C_LONG, MojoBuiltin.C_ULONG):
            width = (
                4 if "windows" in (self._abi.target_triple or "") else self._abi.pointer_size_bytes
            )
        else:
            width = widths.get(name)
        if width is None or self._abi.pointer_size_bytes not in (4, 8):
            return None
        return width, min(width, self._abi.pointer_align_bytes)

    def float_dtype(self, v: FloatType) -> str | None:
        if not self.float_compatible(v):
            return None
        return {
            FloatFormat.BINARY16: "DType.float16",
            FloatFormat.BINARY32: "DType.float32",
            FloatFormat.BINARY64: "DType.float64",
        }.get(self.float_format(v.float_kind))

from ...ir import *


@fieldwise_init
struct TargetQueries(Copyable, Movable):
    var abi: TargetABI

    def default_char_is_unsigned(self) -> Optional[Bool]:
        if not self.abi.target_triple:
            return {}
        var triple = self.abi.target_triple.value().copy()
        return "linux" in triple and (
            triple.startswith("aarch64") or triple.startswith("arm") or triple.startswith("thumb")
        )

    def float_format(self, kind: FloatKind) -> FloatFormat:
        for item in self.abi.float_abi:
            if item.kind == kind:
                return item.format
        # These CIR kinds name the LLVM IEEE types. LONG_DOUBLE is target-defined.
        match kind:
            case .FLOAT16:
                return FloatFormat.BINARY16
            case .FLOAT:
                return FloatFormat.BINARY32
            case .DOUBLE:
                return FloatFormat.BINARY64
            case .FLOAT128:
                return FloatFormat.BINARY128
            case .LONG_DOUBLE:
                return FloatFormat.UNKNOWN

    def float_compatible(self, v: FloatType) -> Bool:
        var format = self.float_format(v.float_kind)
        var width: Int
        match format:
            case .BINARY16:
                width = 2
            case .BINARY32:
                width = 4
            case .BINARY64:
                width = 8
            case .UNKNOWN | .BINARY128 | .X87_EXTENDED | .DOUBLE_DOUBLE:
                return False
        return (
            v.size_bytes == width
            and v.align_bytes
            and v.align_bytes.value() == min(width, self.abi.pointer_align_bytes)
        )

    def supported_c_abi(self) -> Bool:
        if not self.abi.target_triple:
            return False
        var triple = self.abi.target_triple.value().copy()
        return (
            triple.startswith("x86_64-")
            and "linux" in triple
            and self.abi.pointer_size_bytes == 8
            and self.abi.pointer_align_bytes == 8
            and self.abi.byte_order == ByteOrder.LITTLE
        )

    def builtin_layout(self, name: MojoBuiltin) -> Optional[Tuple[Int, Int]]:
        var width: Int
        match name:
            case .NONE | .UNSUPPORTED:
                return {}
            case .BOOL | .UINT8 | .INT8 | .C_CHAR | .C_UCHAR:
                width = 1
            case .FLOAT16 | .C_SHORT | .C_USHORT:
                width = 2
            case .C_INT | .C_UINT | .C_FLOAT:
                width = 4
            case .C_DOUBLE | .C_LONG_LONG | .C_ULONG_LONG:
                width = 8
            case .C_LONG | .C_ULONG:
                width = self.abi.pointer_size_bytes
                if self.abi.target_triple and "windows" in self.abi.target_triple.value():
                    width = 4
            case .INT128 | .UINT128:
                return (16, 16)
        if self.abi.pointer_size_bytes != 4 and self.abi.pointer_size_bytes != 8:
            return {}
        return (width, min(width, self.abi.pointer_align_bytes))

    def float_dtype(self, v: FloatType) -> Optional[String]:
        if not self.float_compatible(v):
            return {}
        match self.float_format(v.float_kind):
            case .BINARY16:
                return String("DType.float16")
            case .BINARY32:
                return String("DType.float32")
            case .BINARY64:
                return String("DType.float64")
            case _:
                return {}

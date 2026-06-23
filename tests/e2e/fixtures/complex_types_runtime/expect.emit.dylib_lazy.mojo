# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
comptime _bindgen_fn_cplx_add = def (lhs: ComplexSIMD[DType.float32, 1], rhs: ComplexSIMD[DType.float32, 1]) thin abi("C") -> ComplexSIMD[DType.float32, 1]
def cplx_add(lhs: ComplexSIMD[DType.float32, 1], rhs: ComplexSIMD[DType.float32, 1]) raises -> ComplexSIMD[DType.float32, 1]
comptime _bindgen_fn_cplx_mul = def (lhs: ComplexSIMD[DType.float32, 1], rhs: ComplexSIMD[DType.float32, 1]) thin abi("C") -> ComplexSIMD[DType.float32, 1]
def cplx_mul(lhs: ComplexSIMD[DType.float32, 1], rhs: ComplexSIMD[DType.float32, 1]) raises -> ComplexSIMD[DType.float32, 1]
comptime _bindgen_fn_cplx_real = def (value: ComplexSIMD[DType.float32, 1]) thin abi("C") -> c_float
def cplx_real(value: ComplexSIMD[DType.float32, 1]) raises -> c_float
comptime _bindgen_fn_cplx_imag = def (value: ComplexSIMD[DType.float32, 1]) thin abi("C") -> c_float
def cplx_imag(value: ComplexSIMD[DType.float32, 1]) raises -> c_float

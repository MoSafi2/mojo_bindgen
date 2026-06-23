# Each non-comment line must be present in the emitted file.
struct _BindgenApi(Movable):
def __init__(out self)
def _ensure_loaded(mut self) raises
def _bindgen_init_api() -> _BindgenApi
comptime _BINDGEN_API = _Global[
def _bindgen_api() -> UnsafePointer[_BindgenApi, MutUntrackedOrigin]
comptime _bindgen_fn_cplx_add = def (lhs: ComplexSIMD[DType.float32, 1], rhs: ComplexSIMD[DType.float32, 1]) thin abi("C") -> ComplexSIMD[DType.float32, 1]
def cplx_add(lhs: ComplexSIMD[DType.float32, 1], rhs: ComplexSIMD[DType.float32, 1]) raises -> ComplexSIMD[DType.float32, 1]
comptime _bindgen_fn_cplx_mul = def (lhs: ComplexSIMD[DType.float32, 1], rhs: ComplexSIMD[DType.float32, 1]) thin abi("C") -> ComplexSIMD[DType.float32, 1]
def cplx_mul(lhs: ComplexSIMD[DType.float32, 1], rhs: ComplexSIMD[DType.float32, 1]) raises -> ComplexSIMD[DType.float32, 1]
comptime _bindgen_fn_cplx_real = def (value: ComplexSIMD[DType.float32, 1]) thin abi("C") -> c_float
def cplx_real(value: ComplexSIMD[DType.float32, 1]) raises -> c_float
comptime _bindgen_fn_cplx_imag = def (value: ComplexSIMD[DType.float32, 1]) thin abi("C") -> c_float
def cplx_imag(value: ComplexSIMD[DType.float32, 1]) raises -> c_float

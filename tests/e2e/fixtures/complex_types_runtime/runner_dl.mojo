from p1_complex_types_runtime_bindings_dl import cplx_add, cplx_imag, cplx_mul, cplx_real
from std.complex import ComplexSIMD


def main() raises:
    var a = ComplexSIMD[DType.float32, 1](1.5, -2.0)
    var b = ComplexSIMD[DType.float32, 1](2.25, 0.5)
    var add_out = cplx_add(a, b)
    var mul_out = cplx_mul(a, b)

    print("cplx_add_real_case0|", cplx_real(add_out))
    print("cplx_add_imag_case0|", cplx_imag(add_out))
    print("cplx_mul_real_case0|", cplx_real(mul_out))
    print("cplx_mul_imag_case0|", cplx_imag(mul_out))

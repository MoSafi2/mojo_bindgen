#ifndef P1_COMPLEX_TYPES_RUNTIME_H
#define P1_COMPLEX_TYPES_RUNTIME_H

_Complex float cplx_add(_Complex float lhs, _Complex float rhs);
_Complex float cplx_mul(_Complex float lhs, _Complex float rhs);
float cplx_real(_Complex float value);
float cplx_imag(_Complex float value);

_Complex double cplx64_add(_Complex double lhs, _Complex double rhs);
double cplx64_real(_Complex double value);
double cplx64_imag(_Complex double value);

#endif

#ifndef P1_COMPLEX_TYPES_RUNTIME_H
#define P1_COMPLEX_TYPES_RUNTIME_H

_Complex float cplx_add(_Complex float lhs, _Complex float rhs);
_Complex float cplx_mul(_Complex float lhs, _Complex float rhs);
float cplx_real(_Complex float value);
float cplx_imag(_Complex float value);

#endif

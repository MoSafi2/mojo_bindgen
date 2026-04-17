#include "input.h"

_Complex float cplx_add(_Complex float lhs, _Complex float rhs) { return lhs + rhs; }

_Complex float cplx_mul(_Complex float lhs, _Complex float rhs) { return lhs * rhs; }

float cplx_real(_Complex float value) { return __real__ value; }

float cplx_imag(_Complex float value) { return __imag__ value; }

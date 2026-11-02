#include "input.h"

_Complex float cplx_add(_Complex float lhs, _Complex float rhs) { return lhs + rhs; }

_Complex float cplx_mul(_Complex float lhs, _Complex float rhs) { return lhs * rhs; }

float cplx_real(_Complex float value) { return __real__ value; }

float cplx_imag(_Complex float value) { return __imag__ value; }

_Complex double cplx64_add(_Complex double lhs, _Complex double rhs) { return lhs + rhs; }
double cplx64_real(_Complex double value) { return __real__ value; }
double cplx64_imag(_Complex double value) { return __imag__ value; }

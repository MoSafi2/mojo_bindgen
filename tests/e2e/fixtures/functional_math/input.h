#ifndef FUNCTIONAL_MATH_H
#define FUNCTIONAL_MATH_H

#include <stdint.h>

int32_t fm_add(int32_t a, int32_t b);
int32_t fm_mix3(int32_t a, int32_t b, int32_t c);
double fm_affine(double x, double scale, double bias);
uint64_t fm_hash_step(uint64_t state, uint64_t value);

#endif

#include "input.h"

int32_t fm_add(int32_t a, int32_t b) { return a + b; }

int32_t fm_mix3(int32_t a, int32_t b, int32_t c) { return (a * 3) + (b * 5) - (c * 7); }

double fm_affine(double x, double scale, double bias) { return (x * scale) + bias; }

uint64_t fm_hash_step(uint64_t state, uint64_t value) {
    const uint64_t prime = 1099511628211ULL;
    return (state ^ value) * prime;
}

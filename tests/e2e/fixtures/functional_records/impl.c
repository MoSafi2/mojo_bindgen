#include "input.h"

fr_point fr_make_point(int32_t x, int32_t y) {
    fr_point p = {x, y};
    return p;
}

fr_pair fr_make_pair(fr_point lhs, fr_point rhs) {
    fr_pair pair = {lhs, rhs};
    return pair;
}

int32_t fr_point_norm1(fr_point p) {
    int32_t ax = p.x < 0 ? -p.x : p.x;
    int32_t ay = p.y < 0 ? -p.y : p.y;
    return ax + ay;
}

fr_pair fr_swap_pair(fr_pair pair) {
    fr_pair out = {pair.rhs, pair.lhs};
    return out;
}

int32_t fr_linear(int32_t x, int32_t scale, int32_t bias) { return (x * scale) + bias; }

int32_t fr_apply_mode(fr_mode mode, int32_t a, int32_t b) {
    if (mode == FR_SUB) {
        return a - b;
    }
    return a + b;
}

bool fr_is_nonzero(int32_t value) { return value != 0; }

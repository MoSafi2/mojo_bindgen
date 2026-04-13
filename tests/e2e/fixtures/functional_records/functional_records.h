#ifndef FUNCTIONAL_RECORDS_H
#define FUNCTIONAL_RECORDS_H

#include <stdbool.h>
#include <stdint.h>

typedef enum fr_mode {
    FR_ADD = 1,
    FR_SUB = 2
} fr_mode;

typedef struct fr_point {
    int32_t x;
    int32_t y;
} fr_point;

typedef struct fr_pair {
    fr_point lhs;
    fr_point rhs;
} fr_pair;

fr_point fr_make_point(int32_t x, int32_t y);
fr_pair fr_make_pair(fr_point lhs, fr_point rhs);
int32_t fr_point_norm1(fr_point p);
fr_pair fr_swap_pair(fr_pair pair);
int32_t fr_linear(int32_t x, int32_t scale, int32_t bias);
int32_t fr_apply_mode(fr_mode mode, int32_t a, int32_t b);
bool fr_is_nonzero(int32_t value);

#endif

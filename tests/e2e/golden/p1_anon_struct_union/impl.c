#include "input.h"

int32_t asu_sanity(int32_t x) {
    asu_wrap value;
    value.b = 2;
    return x + value.b;
}

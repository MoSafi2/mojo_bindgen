#include "input.h"

int32_t cad_sum4(const int32_t values[4]) { return values[0] + values[1] + values[2] + values[3]; }

int32_t cad_sanity(void) {
    const int32_t values[4] = {10, 11, 12, 9};
    return cad_sum4(values);
}

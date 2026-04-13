#include "input.h"

static int32_t pfr_add(int32_t a, int32_t b) { return a + b; }

pfr_binary_op_t pfr_select_add(void) { return pfr_add; }

int32_t pfr_sanity(int32_t x) { return pfr_select_add()(x, 2); }

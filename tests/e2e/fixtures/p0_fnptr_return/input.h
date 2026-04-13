#ifndef P0_FNPTR_RETURN_H
#define P0_FNPTR_RETURN_H

#include <stdint.h>

typedef int32_t (*pfr_binary_op_t)(int32_t, int32_t);

pfr_binary_op_t pfr_select_add(void);
int32_t pfr_sanity(int32_t x);

#endif

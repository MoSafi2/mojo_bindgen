#ifndef P0_PTR_TO_ARRAY_H
#define P0_PTR_TO_ARRAY_H

#include <stdint.h>

extern int32_t (*pta_slot)[1];

int32_t pta_sanity(int32_t x);

#endif

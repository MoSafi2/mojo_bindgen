#include "input.h"

int32_t pta_storage[1] = {7};
int32_t(*pta_slot)[1] = &pta_storage;

int32_t pta_sanity(int32_t x) { return x + (*pta_slot)[0]; }

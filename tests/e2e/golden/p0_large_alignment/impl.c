#include "input.h"

size_t la_align(void) { return __alignof__(la_item); }
size_t la_offset_b(void) { return offsetof(la_item, b); }
int32_t la_sanity(int32_t x) { return x + (int32_t)la_offset_b(); }

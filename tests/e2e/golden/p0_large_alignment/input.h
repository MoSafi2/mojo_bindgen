#ifndef P0_LARGE_ALIGNMENT_H
#define P0_LARGE_ALIGNMENT_H

#include <stddef.h>
#include <stdint.h>

typedef struct la_item {
    uint8_t a;
    uint32_t b __attribute__((aligned(16)));
} la_item;

size_t la_align(void);
size_t la_offset_b(void);
int32_t la_sanity(int32_t x);

#endif

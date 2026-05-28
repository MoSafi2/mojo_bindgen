#ifndef P0_ZERO_LENGTH_TAIL_ACCESS_H
#define P0_ZERO_LENGTH_TAIL_ACCESS_H

#include <stddef.h>
#include <stdint.h>

typedef struct zta_packet {
    uint32_t tag;
    uint8_t payload[0];
} zta_packet;

const zta_packet *zta_fixture(void);
size_t zta_header_size(void);
int32_t zta_sanity(int32_t x);

#endif

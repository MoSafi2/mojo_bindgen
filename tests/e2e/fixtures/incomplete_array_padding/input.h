#ifndef P0_INCOMPLETE_ARRAY_PADDING_H
#define P0_INCOMPLETE_ARRAY_PADDING_H

#include <stddef.h>
#include <stdint.h>

typedef struct iap_packet {
    uint32_t tag;
    uint8_t payload[];
} iap_packet;

size_t iap_header_size(void);
int32_t iap_sanity(int32_t x);

#endif

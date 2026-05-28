#include "input.h"

static const struct {
    uint32_t tag;
    uint8_t payload[3];
} ZTA_FIXTURE = {
    .tag = 11,
    .payload = {9, 4, 2},
};

const zta_packet *zta_fixture(void) { return (const zta_packet *)&ZTA_FIXTURE; }

size_t zta_header_size(void) { return offsetof(zta_packet, payload); }

int32_t zta_sanity(int32_t x) { return x + (int32_t)zta_header_size(); }

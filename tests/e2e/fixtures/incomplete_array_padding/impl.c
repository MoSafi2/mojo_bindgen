#include "input.h"

static const struct {
    uint32_t tag;
    uint8_t payload[3];
} IAP_FIXTURE = {
    .tag = 7,
    .payload = {5, 8, 13},
};

const iap_packet *iap_fixture(void) { return (const iap_packet *)&IAP_FIXTURE; }

size_t iap_header_size(void) { return offsetof(iap_packet, payload); }

int32_t iap_sanity(int32_t x) { return x + (int32_t)iap_header_size(); }

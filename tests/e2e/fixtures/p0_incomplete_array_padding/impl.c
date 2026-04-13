#include "input.h"

size_t iap_header_size(void) { return offsetof(iap_packet, payload); }

int32_t iap_sanity(int32_t x) { return x + (int32_t)iap_header_size(); }

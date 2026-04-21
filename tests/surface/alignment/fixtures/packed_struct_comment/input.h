#include <stdint.h>

typedef struct __attribute__((packed)) psc_header {
    uint8_t tag;
    uint32_t size;
} psc_header;

#include <stdint.h>

typedef struct nrr_payload {
    int32_t values[2];
} nrr_payload;

nrr_payload nrr_build(void);

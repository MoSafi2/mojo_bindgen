#include <stdint.h>

typedef int32_t (*cta_cb_t)(int32_t value);

void cta_install(cta_cb_t cb);

#include <stdint.h>

_Atomic int asf_counter;

struct asf_state {
    _Atomic uint64_t seq;
};

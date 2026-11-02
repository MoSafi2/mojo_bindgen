#include "input.h"
#include <string.h>
static Guarded fixture;
long double extended_global = 1.0L;
Extended *extended_fixture(void) {
    memset(&fixture, 0, sizeof fixture);
    fixture.before = UINT64_C(0x123456789abcdef0);
    fixture.after = UINT64_C(0xfedcba9876543210);
    return fixture.values;
}
void extended_set(Extended *value) {
    value->real = 1.0L / 3.0L;
    __real__ value->pair = 7.0L;
    __imag__ value->pair = -11.0L;
}
int extended_check(Extended *value) {
    return value == &fixture.values[1] && value->real == 1.0L / 3.0L &&
        __real__ value->pair == 7.0L && __imag__ value->pair == -11.0L;
}
int extended_guard(void) {
    return fixture.before == UINT64_C(0x123456789abcdef0) &&
           fixture.after == UINT64_C(0xfedcba9876543210) && fixture.values[0].real == 0.0L;
}
size_t extended_size(void) { return sizeof(Extended); }
size_t extended_align(void) { return _Alignof(Extended); }
size_t extended_stride(void) { return (char *)&fixture.values[1] - (char *)&fixture.values[0]; }

size_t extended_union_size(void) { return sizeof(ExtendedUnion); }
size_t extended_union_align(void) { return _Alignof(ExtendedUnion); }

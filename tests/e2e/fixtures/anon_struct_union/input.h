#ifndef P1_ANON_STRUCT_UNION_H
#define P1_ANON_STRUCT_UNION_H

#include <stdint.h>

typedef struct asu_wrap {
    union {
        struct {
            int32_t b;
        };
    };
} asu_wrap;

int32_t asu_sanity(int32_t x);

#endif

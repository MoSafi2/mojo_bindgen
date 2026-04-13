// Broad weird stress fixture for parser + IR survivability coverage.

#ifndef STRESS_WEIRD_INPUT_H
#define STRESS_WEIRD_INPUT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define EV_PI 3.14159265
#define EV_LABEL "libev"
#define EV_COMBINED (0x1u | 0x2u)
#define EV_NULL ((void *)0)

typedef struct ev_flags {
    unsigned int active : 1;
    unsigned int pending : 1;
    unsigned int priority : 4;
    unsigned int backend : 4;
    unsigned int : 22;
} ev_flags;

struct ev_bf {
    unsigned char a : 3;
    signed int b : 5;
    _Bool c : 1;
};

struct ev_bf2 {
    unsigned int a : 20;
    unsigned int b : 20;
};

struct ev_bf3 {
    unsigned int a : 1;
    unsigned int : 0;
    unsigned int b : 1;
};

int (*ev_ptr_to_array)[10];
int *ev_array_of_ptrs[10];

int ev_legacy(a, b)
int a;
double b;
{
    (void)b;
    return a;
}

inline int ev_inline(int x);
extern inline int ev_extern_inline(int x);

enum ev_big {
    EV_BIG = 0x7FFFFFFFFFFFFFFFLL
};

struct ev_event {
    int type;
    union {
        int fd;
        void *ptr;
    };
};

#endif

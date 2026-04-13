#include "input.h"

int32_t of_sanity(int32_t x, const union of_union *u, const struct of_struct *s) {
    (void)u;
    (void)s;
    return x + 2;
}

int32_t of_probe(void) { return of_sanity(40, 0, 0); }

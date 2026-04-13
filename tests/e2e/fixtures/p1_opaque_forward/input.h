#ifndef P1_OPAQUE_FORWARD_H
#define P1_OPAQUE_FORWARD_H

#include <stdint.h>

union of_union;
struct of_struct;

int32_t of_sanity(int32_t x, const union of_union *u, const struct of_struct *s);
int32_t of_probe(void);

#endif

#ifndef P1_ATOMIC_TYPES_RUNTIME_H
#define P1_ATOMIC_TYPES_RUNTIME_H

#include <stdint.h>

_Atomic int at_counter;

void at_reset(int value);
int at_inc(void);
int at_dec(void);
int at_get(void);
_Atomic int *at_addr(void);
const _Atomic int *at_addr_const(void);
void at_store_ptr(_Atomic int *dst, int value);
int at_load_ptr(const _Atomic int *src);
int at_inc_ptr(_Atomic int *dst);

#endif

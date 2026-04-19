#include "input.h"

void at_reset(int value) { __atomic_store_n(&at_counter, value, __ATOMIC_SEQ_CST); }

int at_inc(void) { return __atomic_add_fetch(&at_counter, 1, __ATOMIC_SEQ_CST); }

int at_dec(void) { return __atomic_sub_fetch(&at_counter, 1, __ATOMIC_SEQ_CST); }

int at_get(void) { return __atomic_load_n(&at_counter, __ATOMIC_SEQ_CST); }

_Atomic int *at_addr(void) { return &at_counter; }

const _Atomic int *at_addr_const(void) { return &at_counter; }

void at_store_ptr(_Atomic int *dst, int value) { __atomic_store_n(dst, value, __ATOMIC_SEQ_CST); }

int at_load_ptr(const _Atomic int *src) { return __atomic_load_n(src, __ATOMIC_SEQ_CST); }

int at_inc_ptr(_Atomic int *dst) { return __atomic_add_fetch(dst, 1, __ATOMIC_SEQ_CST); }

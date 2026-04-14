// Broad weird stress fixture for parser + IR survivability coverage.

#ifndef STRESS_WEIRD_INPUT_H
#define STRESS_WEIRD_INPUT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdatomic.h>
#include <stdint.h>

// Tests float macro preservation in IR.
#define EV_PI 3.14159265
// Tests string macro preservation in IR.
#define EV_LABEL "libev"
// Tests integer binary-expression macro preservation.
#define EV_COMBINED (0x1u | 0x2u)
// Tests nested-parentheses null-pointer macro preservation.
#define EV_NULL ((void *)0)

// Tests dense bitfields plus an anonymous trailing bitfield.
typedef struct ev_flags {
    unsigned int active : 1;
    unsigned int pending : 1;
    unsigned int priority : 4;
    unsigned int backend : 4;
    unsigned int : 22;
} ev_flags;

// Tests mixed backing types in one bitfield-only struct.
struct ev_bf {
    unsigned char a : 3;
    signed int b : 5;
    _Bool c : 1;
};

// Tests wide bitfields spanning multiple storage units.
struct ev_bf2 {
    unsigned int a : 20;
    unsigned int b : 20;
};

// Tests zero-width bitfield alignment / storage reset behavior.
struct ev_bf3 {
    unsigned int a : 1;
    unsigned int : 0;
    unsigned int b : 1;
};

// Tests file-scope pointer-to-array declarator lowering.
int (*ev_ptr_to_array)[10];
// Tests file-scope array-of-pointers declarator lowering.
int *ev_array_of_ptrs[10];

// Tests K&R-style function declaration parsing.
int ev_legacy(a, b)
int a;
double b;
{
    (void)b;
    return a;
}

// Tests plain inline declaration handling.
inline int ev_inline(int x);
// Tests extern inline declaration handling.
extern inline int ev_extern_inline(int x);

// Tests very large enum member value preservation.
enum ev_big {
    EV_BIG = 0x7FFFFFFFFFFFFFFFLL
};

// Tests anonymous union nested directly inside a struct.
struct ev_event {
    int type;
    union {
        int fd;
        void *ptr;
    };
};

// Tests GCC zero-length array as FAM precursor.
struct ev_flex_old {
    int len;
    int data[0];
};

// Tests anonymous union containing anonymous structs.
struct ev_nested_anon {
    int kind;
    union {
        struct { int x; int y; };
        struct { float u; float v; };
    };
};

// Tests struct layout with only an anonymous bitfield member.
struct ev_only_bits {
    unsigned int : 8;
};

// Tests over-aligned struct declaration via _Alignas.
_Alignas(64) struct ev_cacheline {
    int val;
};

// Tests pointer to function returning pointer to array.
int (*(*ev_fp_returning_arr)(void))[5];
// Tests array of function pointers.
int (*ev_dispatch_table[8])(int);
// Tests pointer to function pointer.
int (**ev_fp_ptr)(void);

// Tests combined const+volatile pointee qualifiers.
const volatile int *ev_cv_ptr;
// Tests const pointer global with initializer.
int * const ev_const_ptr = 0;
// Tests const pointee plus const pointer global.
int const * const ev_const_both = 0;

// Tests plain _Atomic scalar lowering at file scope.
_Atomic int ev_atomic_int;
// Tests function-style _Atomic(T) spelling at file scope.
_Atomic(uint64_t) ev_atomic_u64;

// Tests _Atomic fields inside a struct.
struct ev_concurrent {
    _Atomic int refcount;
    _Atomic(void *) next;
};

// Tests enum with negative values.
enum ev_signed_enum {
    EV_NEG = -1,
    EV_ZERO = 0,
    EV_POS = 1
};

// Tests enum members defined by constant expressions and references.
enum ev_computed {
    EV_A = 1 << 0,
    EV_B = 1 << 1,
    EV_C = EV_A | EV_B
};

// Tests sparse / non-contiguous enum values.
enum ev_sparse {
    EV_S1 = 0,
    EV_S2 = 100,
    EV_S3 = 200
};

// Tests _Noreturn function declaration handling.
_Noreturn void ev_die(const char *msg);
// Tests visibility attribute on a function declaration.
__attribute__((visibility("default"))) int ev_exported(void);
// Tests deprecated attribute on a function declaration.
__attribute__((deprecated("use ev_new instead"))) void ev_old(void);
// Tests nonnull attribute on a function declaration.
__attribute__((nonnull(1, 2))) void ev_nonnull(int *a, int *b);

// Tests C11 static assertion parsing in the header stream.
_Static_assert(sizeof(int) >= 4, "int must be at least 4 bytes");
// Tests static assertion that references an earlier declaration.
_Static_assert(sizeof(ev_flags) <= 8, "ev_flags too large");

// Tests typedef to array type.
typedef int ev_pair[2];
// Tests typedef to qualified pointer type.
typedef const char *ev_cstring;
// Tests typedef to volatile integer type.
typedef volatile uint32_t ev_vreg;

// Tests variadic function declaration lowering.
int ev_log(const char *fmt, ...);
// Tests VLA parameter declarator handling.
void ev_vla_fn(int n, int arr[n]);
// Tests static array parameter qualifier handling.
void ev_static_arr(int arr[static 4]);

// Tests compound-literal initializer on a global.
static const int *ev_defaults = (int[]){1, 2, 3, 4};

// Tests designated-initializer target record declaration.
struct ev_default_event {
    int type;
    int fd;
};

// Tests designated initializer on a global record variable.
struct ev_default_event ev_default_event_value = {
    .type = 0,
    .fd = -1
};

// Tests GCC __typeof__ extension lowering.
__typeof__(int *) ev_typeof_ptr;

#endif

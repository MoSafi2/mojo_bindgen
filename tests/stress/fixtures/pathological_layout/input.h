// Pathological parser/codegen stress fixture focused on layout edge cases.

#ifndef PATHOLOGICAL_LAYOUT_INPUT_H
#define PATHOLOGICAL_LAYOUT_INPUT_H

#include <stdbool.h>
#include <stdint.h>

// Dense bitfields plus a zero-width barrier should preserve both logical members and resets.
struct pl_dense_bits {
    unsigned ready : 1;
    unsigned error : 1;
    unsigned state : 3;
    unsigned code : 11;
    unsigned : 0;
    unsigned epoch : 8;
};

// Mixed bitfield backing types exercise storage splitting logic.
struct pl_mixed_bits {
    unsigned char a : 3;
    signed int b : 5;
    _Bool c : 1;
};

// Pure bitfield records should still stay as first-class declarations.
struct pl_pure_bits {
    unsigned flag : 1;
    unsigned mode : 3;
};

// Anonymous-only bitfields must not disappear during lowering.
struct pl_zero_width_only {
    unsigned : 8;
};

// Straddle bitfields exercise storage splitting logic.
struct pl_straddle_probe {
    unsigned a : 31;
    unsigned b : 2;
};

// Trailing zero-width bitfields exercise storage splitting logic.
struct pl_trailing_zero_width {
    unsigned a : 5;
    unsigned : 0;
};

// Packed declarations feed alignment-policy comments in emitted Mojo.
struct __attribute__((packed)) pl_packed_header {
    uint8_t tag;
    uint32_t size;
};

// Explicit record alignment should be visible in both IR and strict/portable emission.
struct __attribute__((aligned(16))) pl_explicit_align {
    char tag;
    int value;
};

// Field-level alignment changes record layout without an explicit record request.
struct pl_field_align {
    char tag;
    int value __attribute__((aligned(16)));
};

// Packed + explicit align is useful for strict-vs-portable policy coverage.
struct __attribute__((packed, aligned(16))) pl_packed_aligned {
    uint8_t tag;
    uint32_t size;
};

// Flexible arrays and zero-length arrays stress incomplete tail storage forms.
struct pl_flex {
    uint32_t size;
    uint8_t data[];
};

struct pl_incomplete_array {
    uint32_t size;
    uint8_t data[0];
};

// Pointer-to-array plus array-of-pointers declarators are layout-adjacent parser traps.
typedef int pl_row4[4];

struct pl_ptr_array_holder {
    int (*ptr_to_array)[4];
    int *array_of_ptrs[4];
};


#endif

// Pathological parser/codegen stress fixture focused on declaration topology.
// Each declaration exists because bindgen code commonly regresses on it.

#ifndef PATHOLOGICAL_CORE_INPUT_H
#define PATHOLOGICAL_CORE_INPUT_H

#include <complex.h>
#include <stdatomic.h>
#include <stdint.h>

// Repeated forward declarations should not duplicate opaque handles.
struct pc_incomplete;
struct pc_incomplete;
union pc_forward_union;

// Callback typedef layering should preserve the public alias name.
typedef int (*pc_callback_t)(struct pc_incomplete *node, int reason);
typedef pc_callback_t pc_callback_alias_t;
typedef pc_callback_alias_t pc_callback_chain_t;

// Extension vectors and complex scalars should stay modeled, not collapsed away.
typedef float pc_vec4 __attribute__((vector_size(16)));
typedef double _Complex pc_complex64;

// Anonymous union carriers need stable synthetic names.
struct pc_nested_anon {
    int tag;
    union {
        struct {
            int x;
            int y;
        };
        struct {
            float u;
            float v;
        };
    };
};

// Recursive records plus inner unions are easy to break when naming anonymous layouts.
struct pc_recursive_node {
    struct pc_recursive_node *next;
    union {
        int as_int;
        struct {
            short left;
            short right;
        } pair;
    } payload;
};

// By-value unions currently lower through layout-preserving fallback paths.
union pc_inline_array_fallback {
    uint8_t bytes[16];
    double scalars[2];
};

// Pointer-to-array and function-pointer-return forms must survive lowering intact.
struct pc_dispatch_entry {
    pc_callback_chain_t cb;
    int (*(*choose)(int which))(int);
    int (*ptr_to_array)[8];
};

// Atomic fields exercise parser and codegen policy together.
struct pc_atomic_payload {
    _Atomic int counter;
    _Atomic(void *) next;
};

// Globals referencing incomplete and extension-heavy types should remain reachable.
extern struct pc_incomplete *pc_global_incomplete;
extern union pc_forward_union *pc_global_union;
extern union pc_inline_array_fallback pc_global_payload;
extern pc_vec4 pc_global_vector;

// File-scope declarators covering awkward pointer/array/function combinations.
extern int (*pc_ptr_to_array)[8];
int (*(*pc_fn_returning_array_ptr)(void))[5];
pc_callback_t pc_choose_callback(int which);
pc_callback_t pc_choose_callback(int which);
int (*pc_pick_transform(int which))(int);
pc_complex64 pc_complex_mul(pc_complex64 a, pc_complex64 b);
void pc_consume_vector(pc_vec4 lanes);

#endif

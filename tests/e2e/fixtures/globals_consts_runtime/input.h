#ifndef GCR_GLOBALS_CONSTS_RUNTIME_H
#define GCR_GLOBALS_CONSTS_RUNTIME_H

#include <stdint.h>

extern int32_t gcr_mut;
extern const int32_t gcr_limit;

typedef float gcr_vec4 __attribute__((vector_size(16)));
extern const gcr_vec4 gcr_vec_const;
extern gcr_vec4 gcr_vec_mut;

extern _Atomic int gcr_atomic;

#endif

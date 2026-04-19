#include "input.h"

int32_t gcr_mut = 10;
const int32_t gcr_limit = 42;

const gcr_vec4 gcr_vec_const = {1.0f, 2.0f, 3.0f, 4.0f};
gcr_vec4 gcr_vec_mut = {0.5f, 1.5f, 2.5f, 3.5f};

_Atomic int gcr_atomic = 100;

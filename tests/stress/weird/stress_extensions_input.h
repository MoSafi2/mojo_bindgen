// Stress fixture for extension and currently mixed-support types.

#ifndef STRESS_EXTENSIONS_INPUT_H
#define STRESS_EXTENSIONS_INPUT_H

typedef float float4 __attribute__((vector_size(16)));
typedef int int4 __attribute__((vector_size(16)));

struct ext_payload {
    float4 lane_values;
    int4 lane_indices;
};

_Complex float ext_complex_add(_Complex float a, _Complex float b);
void ext_consume_vector(float4 values);

#endif

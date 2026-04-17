#ifndef P1_VECTOR_EXTENSION_TYPES_RUNTIME_H
#define P1_VECTOR_EXTENSION_TYPES_RUNTIME_H

typedef float vet_float4 __attribute__((vector_size(16)));

float vet_sum(vet_float4 value);
vet_float4 vet_add(vet_float4 lhs, vet_float4 rhs);
vet_float4 vet_mul(vet_float4 lhs, vet_float4 rhs);
float vet_add_sum_case0(void);
float vet_mul_sum_case0(void);

#endif

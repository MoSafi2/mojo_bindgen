#include "input.h"

static float vet_sum_impl(vet_float4 value) { return value[0] + value[1] + value[2] + value[3]; }

float vet_sum(vet_float4 value) { return vet_sum_impl(value); }

vet_float4 vet_add(vet_float4 lhs, vet_float4 rhs) { return lhs + rhs; }

vet_float4 vet_mul(vet_float4 lhs, vet_float4 rhs) { return lhs * rhs; }

float vet_add_sum_case0(void) {
    vet_float4 lhs = {1.0f, 2.0f, 3.0f, 4.0f};
    vet_float4 rhs = {5.0f, 6.0f, 7.0f, 8.0f};
    return vet_sum_impl(vet_add(lhs, rhs));
}

float vet_mul_sum_case0(void) {
    vet_float4 lhs = {1.0f, 2.0f, 3.0f, 4.0f};
    vet_float4 rhs = {5.0f, 6.0f, 7.0f, 8.0f};
    return vet_sum_impl(vet_mul(lhs, rhs));
}

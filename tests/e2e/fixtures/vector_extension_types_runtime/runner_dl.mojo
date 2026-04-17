from vector_extension_types_runtime_bindings_dl import (
    vet_add,
    vet_add_sum_case0,
    vet_float4,
    vet_mul,
    vet_mul_sum_case0,
    vet_sum,
)


def main() raises:
    var lhs = vet_float4(1.0, 2.0, 3.0, 4.0)
    var rhs = vet_float4(5.0, 6.0, 7.0, 8.0)
    var add = vet_add(lhs, rhs)
    var mul = vet_mul(lhs, rhs)
    print("vet_sum_case0|", vet_sum(lhs))
    print("vet_add_lane0_case0|", add[0])
    print("vet_add_lane3_case0|", add[3])
    print("vet_mul_lane0_case0|", mul[0])
    print("vet_mul_lane3_case0|", mul[3])
    print("vet_add_sum_case0|", vet_add_sum_case0())
    print("vet_mul_sum_case0|", vet_mul_sum_case0())

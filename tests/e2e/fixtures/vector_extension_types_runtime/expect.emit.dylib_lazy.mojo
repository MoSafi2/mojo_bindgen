# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
comptime _bindgen_fn_vet_sum = def (value: vet_float4) thin abi("C") -> c_float
def vet_sum(value: vet_float4) raises -> c_float
comptime _bindgen_fn_vet_add = def (lhs: vet_float4, rhs: vet_float4) thin abi("C") -> vet_float4
def vet_add(lhs: vet_float4, rhs: vet_float4) raises -> vet_float4
comptime _bindgen_fn_vet_mul = def (lhs: vet_float4, rhs: vet_float4) thin abi("C") -> vet_float4
def vet_mul(lhs: vet_float4, rhs: vet_float4) raises -> vet_float4
comptime _bindgen_fn_vet_add_sum_case0 = def () thin abi("C") -> c_float
def vet_add_sum_case0() raises -> c_float
comptime _bindgen_fn_vet_mul_sum_case0 = def () thin abi("C") -> c_float
def vet_mul_sum_case0() raises -> c_float

# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
comptime _bindgen_fn_fm_add = def (a: int32_t, b: int32_t) thin abi("C") -> int32_t
def fm_add(a: int32_t, b: int32_t) raises -> int32_t
comptime _bindgen_fn_fm_mix3 = def (a: int32_t, b: int32_t, c: int32_t) thin abi("C") -> int32_t
def fm_mix3(a: int32_t, b: int32_t, c: int32_t) raises -> int32_t
comptime _bindgen_fn_fm_affine = def (x: c_double, scale: c_double, bias: c_double) thin abi("C") -> c_double
def fm_affine(x: c_double, scale: c_double, bias: c_double) raises -> c_double
comptime _bindgen_fn_fm_hash_step = def (state: uint64_t, value: uint64_t) thin abi("C") -> uint64_t
def fm_hash_step(state: uint64_t, value: uint64_t) raises -> uint64_t

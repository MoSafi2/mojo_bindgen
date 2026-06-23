# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
comptime _bindgen_fn_fr_make_point = def (x: int32_t, y: int32_t) thin abi("C") -> fr_point
def fr_make_point(x: int32_t, y: int32_t) raises -> fr_point
comptime _bindgen_fn_fr_make_pair = def (lhs: fr_point, rhs: fr_point) thin abi("C") -> fr_pair
def fr_make_pair(lhs: fr_point, rhs: fr_point) raises -> fr_pair
comptime _bindgen_fn_fr_point_norm1 = def (p: fr_point) thin abi("C") -> int32_t
def fr_point_norm1(p: fr_point) raises -> int32_t
comptime _bindgen_fn_fr_swap_pair = def (pair: fr_pair) thin abi("C") -> fr_pair
def fr_swap_pair(pair: fr_pair) raises -> fr_pair
comptime _bindgen_fn_fr_linear = def (x: int32_t, scale: int32_t, bias: int32_t) thin abi("C") -> int32_t
def fr_linear(x: int32_t, scale: int32_t, bias: int32_t) raises -> int32_t
comptime _bindgen_fn_fr_apply_mode = def (mode: fr_mode, a: int32_t, b: int32_t) thin abi("C") -> int32_t
def fr_apply_mode(mode: fr_mode, a: int32_t, b: int32_t) raises -> int32_t
comptime _bindgen_fn_fr_is_nonzero = def (value: int32_t) thin abi("C") -> Bool
def fr_is_nonzero(value: int32_t) raises -> Bool

# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
comptime _bindgen_fn_pfr_select_add = def () thin abi("C") -> pfr_binary_op_t
def pfr_select_add() raises -> pfr_binary_op_t
comptime _bindgen_fn_pfr_sanity = def (x: int32_t) thin abi("C") -> int32_t
def pfr_sanity(x: int32_t) raises -> int32_t

# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
comptime _bindgen_fn_cad_sum4 = def (values: InlineArray[int32_t, 4]) thin abi("C") -> int32_t
def cad_sum4(values: InlineArray[int32_t, 4]) raises -> int32_t
comptime _bindgen_fn_cad_sanity = def () thin abi("C") -> int32_t
def cad_sanity() raises -> int32_t

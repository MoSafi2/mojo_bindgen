# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
comptime _bindgen_fn_of_sanity = def (x: int32_t, u: Optional[UnsafePointer[of_union, ImmutUntrackedOrigin]], s: Optional[UnsafePointer[of_struct, ImmutUntrackedOrigin]]) thin abi("C") -> int32_t
def of_sanity(x: int32_t, u: Optional[UnsafePointer[of_union, ImmutUntrackedOrigin]], s: Optional[UnsafePointer[of_struct, ImmutUntrackedOrigin]]) raises -> int32_t
comptime _bindgen_fn_of_probe = def () thin abi("C") -> int32_t
def of_probe() raises -> int32_t

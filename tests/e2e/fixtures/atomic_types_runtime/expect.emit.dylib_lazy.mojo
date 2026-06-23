# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
comptime _bindgen_fn_at_reset = def (value: c_int) thin abi("C") -> None
def at_reset(value: c_int) raises -> None
comptime _bindgen_fn_at_inc = def () thin abi("C") -> c_int
def at_inc() raises -> c_int
comptime _bindgen_fn_at_dec = def () thin abi("C") -> c_int
def at_dec() raises -> c_int
comptime _bindgen_fn_at_get = def () thin abi("C") -> c_int
def at_get() raises -> c_int
comptime _bindgen_fn_at_addr = def () thin abi("C") -> Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]]
def at_addr() raises -> Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]]
comptime _bindgen_fn_at_addr_const = def () thin abi("C") -> Optional[UnsafePointer[Atomic[DType.int32], ImmutUntrackedOrigin]]
def at_addr_const() raises -> Optional[UnsafePointer[Atomic[DType.int32], ImmutUntrackedOrigin]]
comptime _bindgen_fn_at_store_ptr = def (dst: Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]], value: c_int) thin abi("C") -> None
def at_store_ptr(dst: Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]], value: c_int) raises -> None
comptime _bindgen_fn_at_load_ptr = def (src: Optional[UnsafePointer[Atomic[DType.int32], ImmutUntrackedOrigin]]) thin abi("C") -> c_int
def at_load_ptr(src: Optional[UnsafePointer[Atomic[DType.int32], ImmutUntrackedOrigin]]) raises -> c_int
comptime _bindgen_fn_at_inc_ptr = def (dst: Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]]) thin abi("C") -> c_int
def at_inc_ptr(dst: Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]]) raises -> c_int

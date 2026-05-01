# Each non-comment line must be present in the emitted file.
# global variable at_counter: Atomic[DType.int32] (atomic global requires manual binding (use Atomic APIs on a pointer))
def at_reset(
def at_inc(
def at_dec(
def at_get(
def at_addr() raises -> Optional[UnsafePointer[Atomic[DType.int32], MutExternalOrigin]]:
def at_addr_const() raises -> Optional[UnsafePointer[Atomic[DType.int32], ImmutExternalOrigin]]:
def at_store_ptr(dst: Optional[UnsafePointer[Atomic[DType.int32], MutExternalOrigin]], value: c_int) raises -> None:
def at_load_ptr(src: Optional[UnsafePointer[Atomic[DType.int32], ImmutExternalOrigin]]) raises -> c_int:
def at_inc_ptr(dst: Optional[UnsafePointer[Atomic[DType.int32], MutExternalOrigin]]) raises -> c_int:

# Each non-comment line must be present in the emitted file.
# global variable at_counter: Atomic[DType.int32] (atomic global requires manual binding (use Atomic APIs on a pointer))
def at_reset(
def at_inc(
def at_dec(
def at_get(
def at_addr() -> Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]]:
def at_addr_const() -> Optional[UnsafePointer[Atomic[DType.int32], ImmutUntrackedOrigin]]:
def at_store_ptr(dst: Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]], value: c_int) -> None:
def at_load_ptr(src: Optional[UnsafePointer[Atomic[DType.int32], ImmutUntrackedOrigin]]) -> c_int:
def at_inc_ptr(dst: Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]]) -> c_int:

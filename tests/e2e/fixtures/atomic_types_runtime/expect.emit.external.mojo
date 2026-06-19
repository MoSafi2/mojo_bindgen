# Each non-comment line must be present in the emitted file.
# global variable at_counter: Atomic[DType.int32] (atomic global requires manual binding (use Atomic APIs on a pointer))
def at_reset(
def at_inc(
def at_dec(
def at_get(
def at_addr() abi("C") -> Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]]:
def at_addr_const() abi("C") -> Optional[UnsafePointer[Atomic[DType.int32], ImmutUntrackedOrigin]]:
def at_store_ptr(dst: Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]], value: c_int) abi("C") -> None:
def at_load_ptr(src: Optional[UnsafePointer[Atomic[DType.int32], ImmutUntrackedOrigin]]) abi("C") -> c_int:
def at_inc_ptr(dst: Optional[UnsafePointer[Atomic[DType.int32], MutUntrackedOrigin]]) abi("C") -> c_int:

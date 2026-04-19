# Each non-comment line must be present in the emitted file.
# global variable at_counter: Atomic[DType.int32] (atomic global requires manual binding (use Atomic APIs on a pointer))
def at_reset(
def at_inc(
def at_dec(
def at_get(
def at_addr() abi("C") -> UnsafePointer[Atomic[DType.int32], MutExternalOrigin]:
def at_addr_const() abi("C") -> UnsafePointer[Atomic[DType.int32], ImmutExternalOrigin]:
def at_store_ptr(dst: UnsafePointer[Atomic[DType.int32], MutExternalOrigin], value: c_int) abi("C") -> None:
def at_load_ptr(src: UnsafePointer[Atomic[DType.int32], ImmutExternalOrigin]) abi("C") -> c_int:
def at_inc_ptr(dst: UnsafePointer[Atomic[DType.int32], MutExternalOrigin]) abi("C") -> c_int:

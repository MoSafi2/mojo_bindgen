# Each non-comment line must be present in the emitted file.
# global variable at_counter: Atomic[c_int] (atomic global requires manual binding (use Atomic APIs on a pointer))
def at_reset(
def at_inc(
def at_dec(
def at_get(
def at_addr() abi("C") -> Optional[Pointer[Atomic[c_int], MutUntrackedOrigin]]:
def at_addr_const() abi("C") -> Optional[Pointer[Atomic[c_int], ImmUntrackedOrigin]]:
def at_store_ptr(dst: Optional[Pointer[Atomic[c_int], MutUntrackedOrigin]], value: c_int) abi("C") -> None:
def at_load_ptr(src: Optional[Pointer[Atomic[c_int], ImmUntrackedOrigin]]) abi("C") -> c_int:
def at_inc_ptr(dst: Optional[Pointer[Atomic[c_int], MutUntrackedOrigin]]) abi("C") -> c_int:

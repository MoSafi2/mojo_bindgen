# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
def payload_offset() -> UInt
def payload_ptr(base: UnsafePointer[zta_packet, ImmutUntrackedOrigin]) -> UnsafePointer[uint8_t, ImmutUntrackedOrigin]
def payload_mut_ptr(base: UnsafePointer[zta_packet, MutUntrackedOrigin]) -> UnsafePointer[uint8_t, MutUntrackedOrigin]
comptime _bindgen_fn_zta_fixture = def () thin abi("C") -> Optional[UnsafePointer[zta_packet, ImmutUntrackedOrigin]]
def zta_fixture() raises -> Optional[UnsafePointer[zta_packet, ImmutUntrackedOrigin]]
comptime _bindgen_fn_zta_header_size = def () thin abi("C") -> size_t
def zta_header_size() raises -> size_t
comptime _bindgen_fn_zta_sanity = def (x: int32_t) thin abi("C") -> int32_t
def zta_sanity(x: int32_t) raises -> int32_t

# Each non-comment line must be present in the emitted file.
def _bindgen_init_dylib() -> OwnedDLHandle
comptime _BINDGEN_DYLIB = _Global[
def _raw() raises -> UnsafePointer[Self.T, MutUntrackedOrigin]
def ptr() raises -> UnsafePointer[Self.T, MutUntrackedOrigin]
def load() raises -> Self.T
def store(value: Self.T) raises -> None
def _raw() raises -> UnsafePointer[Self.T, MutUntrackedOrigin]
def ptr() raises -> UnsafePointer[Self.T, ImmutUntrackedOrigin]
def load() raises -> Self.T

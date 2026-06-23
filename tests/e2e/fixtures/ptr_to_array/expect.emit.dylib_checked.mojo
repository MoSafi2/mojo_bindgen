# Each non-comment line must be present in the emitted file.
struct _BindgenApi(Movable):
def __init__(out self)
def _ensure_loaded(mut self) raises
def _bindgen_init_api() -> _BindgenApi
comptime _BINDGEN_API = _Global[
def _bindgen_api() -> UnsafePointer[_BindgenApi, MutUntrackedOrigin]
def _raw() raises -> UnsafePointer[Self.T, MutUntrackedOrigin]
def ptr() raises -> UnsafePointer[Self.T, MutUntrackedOrigin]
def load() raises -> Self.T
def store(value: Self.T) raises -> None
def _raw() raises -> UnsafePointer[Self.T, MutUntrackedOrigin]
def ptr() raises -> UnsafePointer[Self.T, ImmutUntrackedOrigin]
def load() raises -> Self.T
comptime _bindgen_fn_pta_sanity = def (x: int32_t) thin abi("C") -> int32_t
def pta_sanity(x: int32_t) raises -> int32_t

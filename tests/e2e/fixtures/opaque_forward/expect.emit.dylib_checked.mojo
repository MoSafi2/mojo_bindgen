# Each non-comment line must be present in the emitted file.
struct _BindgenApi(Movable):
def __init__(out self)
def _ensure_loaded(mut self) raises
def _bindgen_init_api() -> _BindgenApi
comptime _BINDGEN_API = _Global[
def _bindgen_api() -> UnsafePointer[_BindgenApi, MutUntrackedOrigin]
comptime _bindgen_fn_of_sanity = def (x: int32_t, u: Optional[UnsafePointer[of_union, ImmutUntrackedOrigin]], s: Optional[UnsafePointer[of_struct, ImmutUntrackedOrigin]]) thin abi("C") -> int32_t
def of_sanity(x: int32_t, u: Optional[UnsafePointer[of_union, ImmutUntrackedOrigin]], s: Optional[UnsafePointer[of_struct, ImmutUntrackedOrigin]]) raises -> int32_t
comptime _bindgen_fn_of_probe = def () thin abi("C") -> int32_t
def of_probe() raises -> int32_t

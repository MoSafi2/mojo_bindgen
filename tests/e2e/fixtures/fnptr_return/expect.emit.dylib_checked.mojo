# Each non-comment line must be present in the emitted file.
struct _BindgenApi(Movable):
def __init__(out self)
def _ensure_loaded(mut self) raises
def _bindgen_init_api() -> _BindgenApi
comptime _BINDGEN_API = _Global[
def _bindgen_api() -> UnsafePointer[_BindgenApi, MutUntrackedOrigin]
comptime _bindgen_fn_pfr_select_add = def () thin abi("C") -> pfr_binary_op_t
def pfr_select_add() raises -> pfr_binary_op_t
comptime _bindgen_fn_pfr_sanity = def (x: int32_t) thin abi("C") -> int32_t
def pfr_sanity(x: int32_t) raises -> int32_t

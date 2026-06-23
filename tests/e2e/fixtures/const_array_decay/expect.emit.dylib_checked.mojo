# Each non-comment line must be present in the emitted file.
struct _BindgenApi(Movable):
def __init__(out self)
def _ensure_loaded(mut self) raises
def _bindgen_init_api() -> _BindgenApi
comptime _BINDGEN_API = _Global[
def _bindgen_api() -> UnsafePointer[_BindgenApi, MutUntrackedOrigin]
comptime _bindgen_fn_cad_sum4 = def (values: InlineArray[int32_t, 4]) thin abi("C") -> int32_t
def cad_sum4(values: InlineArray[int32_t, 4]) raises -> int32_t
comptime _bindgen_fn_cad_sanity = def () thin abi("C") -> int32_t
def cad_sanity() raises -> int32_t

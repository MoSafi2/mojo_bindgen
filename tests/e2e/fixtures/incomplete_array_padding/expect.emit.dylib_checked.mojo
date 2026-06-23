# Each non-comment line must be present in the emitted file.
struct _BindgenApi(Movable):
def __init__(out self)
def _ensure_loaded(mut self) raises
def _bindgen_init_api() -> _BindgenApi
comptime _BINDGEN_API = _Global[
def _bindgen_api() -> UnsafePointer[_BindgenApi, MutUntrackedOrigin]
def payload_offset() -> UInt
def payload_ptr(base: UnsafePointer[iap_packet, ImmutUntrackedOrigin]) -> UnsafePointer[uint8_t, ImmutUntrackedOrigin]
def payload_mut_ptr(base: UnsafePointer[iap_packet, MutUntrackedOrigin]) -> UnsafePointer[uint8_t, MutUntrackedOrigin]
comptime _bindgen_fn_iap_fixture = def () thin abi("C") -> Optional[UnsafePointer[iap_packet, ImmutUntrackedOrigin]]
def iap_fixture() raises -> Optional[UnsafePointer[iap_packet, ImmutUntrackedOrigin]]
comptime _bindgen_fn_iap_header_size = def () thin abi("C") -> size_t
def iap_header_size() raises -> size_t
comptime _bindgen_fn_iap_sanity = def (x: int32_t) thin abi("C") -> int32_t
def iap_sanity(x: int32_t) raises -> int32_t

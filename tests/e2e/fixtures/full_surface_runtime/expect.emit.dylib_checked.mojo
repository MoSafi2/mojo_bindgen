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
def __init__(out self)
def __init__(out self, active: c_uint, pending: c_uint, priority: c_uint, backend: c_uint)
def active(self) -> c_uint
def set_active(mut self, value: c_uint)
def pending(self) -> c_uint
def set_pending(mut self, value: c_uint)
def priority(self) -> c_uint
def set_priority(mut self, value: c_uint)
def backend(self) -> c_uint
def set_backend(mut self, value: c_uint)
comptime _bindgen_fn_surf_add = def (a: surf_alias_i32, b: surf_alias_i32) thin abi("C") -> int32_t
def surf_add(a: surf_alias_i32, b: surf_alias_i32) raises -> int32_t
comptime _bindgen_fn_surf_affine = def (x: c_double, scale: c_double, bias: c_double) thin abi("C") -> c_double
def surf_affine(x: c_double, scale: c_double, bias: c_double) raises -> c_double
comptime _bindgen_fn_surf_apply_mode = def (mode: surf_mode, a: int32_t, b: int32_t) thin abi("C") -> int32_t
def surf_apply_mode(mode: surf_mode, a: int32_t, b: int32_t) raises -> int32_t
comptime _bindgen_fn_surf_is_nonzero = def (value: int32_t) thin abi("C") -> Bool
def surf_is_nonzero(value: int32_t) raises -> Bool
comptime _bindgen_fn_surf_union_from_int = def (value: int32_t) thin abi("C") -> int32_t
def surf_union_from_int(value: int32_t) raises -> int32_t
comptime _bindgen_fn_surf_flags_score = def (active: c_uint, pending: c_uint, priority: c_uint, backend: c_uint) thin abi("C") -> int32_t
def surf_flags_score(active: c_uint, pending: c_uint, priority: c_uint, backend: c_uint) raises -> int32_t
comptime _bindgen_fn_surf_packed_sum = def (flag: uint8_t, length: uint32_t) thin abi("C") -> int32_t
def surf_packed_sum(flag: uint8_t, length: uint32_t) raises -> int32_t
comptime _bindgen_fn_surf_matrix_trace = def (a00: c_float, a11: c_float, a22: c_float, a33: c_float) thin abi("C") -> int32_t
def surf_matrix_trace(a00: c_float, a11: c_float, a22: c_float, a33: c_float) raises -> int32_t
comptime _bindgen_fn_surf_global_plus = def (x: int32_t) thin abi("C") -> int32_t
def surf_global_plus(x: int32_t) raises -> int32_t
comptime _bindgen_fn_surf_fill_series = def (out_: Optional[UnsafePointer[int32_t, MutUntrackedOrigin]], n: int32_t, start: int32_t, step: int32_t) thin abi("C") -> None
def surf_fill_series(out_: Optional[UnsafePointer[int32_t, MutUntrackedOrigin]], n: int32_t, start: int32_t, step: int32_t) raises -> None
comptime _bindgen_fn_surf_sum_array = def (values: Optional[UnsafePointer[int32_t, ImmutUntrackedOrigin]], n: int32_t) thin abi("C") -> int32_t
def surf_sum_array(values: Optional[UnsafePointer[int32_t, ImmutUntrackedOrigin]], n: int32_t) raises -> int32_t
comptime _bindgen_fn_surf_count_nonzero = def (values: Optional[UnsafePointer[int32_t, MutUntrackedOrigin]], n: int32_t) thin abi("C") -> int32_t
def surf_count_nonzero(values: Optional[UnsafePointer[int32_t, MutUntrackedOrigin]], n: int32_t) raises -> int32_t
comptime _bindgen_fn_surf_memory_copy = def (dest: Optional[MutOpaquePointer[MutUntrackedOrigin]], src: Optional[ImmutOpaquePointer[ImmutUntrackedOrigin]], n: size_t) thin abi("C") -> None
def surf_memory_copy(dest: Optional[MutOpaquePointer[MutUntrackedOrigin]], src: Optional[ImmutOpaquePointer[ImmutUntrackedOrigin]], n: size_t) raises -> None
comptime _bindgen_fn_surf_get_message = def (out_msg: Optional[UnsafePointer[Optional[UnsafePointer[c_char, MutUntrackedOrigin]], MutUntrackedOrigin]], out_len: Optional[UnsafePointer[int32_t, MutUntrackedOrigin]]) thin abi("C") -> None
def surf_get_message(out_msg: Optional[UnsafePointer[Optional[UnsafePointer[c_char, MutUntrackedOrigin]], MutUntrackedOrigin]], out_len: Optional[UnsafePointer[int32_t, MutUntrackedOrigin]]) raises -> None
comptime _bindgen_fn_surf_handle_new = def (seed: int32_t) thin abi("C") -> Optional[UnsafePointer[surf_handle, MutUntrackedOrigin]]
def surf_handle_new(seed: int32_t) raises -> Optional[UnsafePointer[surf_handle, MutUntrackedOrigin]]
comptime _bindgen_fn_surf_handle_get = def (handle: Optional[UnsafePointer[surf_handle, ImmutUntrackedOrigin]]) thin abi("C") -> int32_t
def surf_handle_get(handle: Optional[UnsafePointer[surf_handle, ImmutUntrackedOrigin]]) raises -> int32_t
comptime _bindgen_fn_surf_handle_free = def (handle: Optional[UnsafePointer[surf_handle, MutUntrackedOrigin]]) thin abi("C") -> None
def surf_handle_free(handle: Optional[UnsafePointer[surf_handle, MutUntrackedOrigin]]) raises -> None
comptime _bindgen_fn_surf_install_callback = def (cb: surf_cb_t, userdata: Optional[MutOpaquePointer[MutUntrackedOrigin]]) thin abi("C") -> None
def surf_install_callback(cb: surf_cb_t, userdata: Optional[MutOpaquePointer[MutUntrackedOrigin]]) raises -> None
comptime _bindgen_fn_surf_variadic_sum = def (count: int32_t) thin abi("C") -> int32_t
def surf_variadic_sum(count: int32_t) raises -> int32_t
comptime _bindgen_fn_surf_inline_double = def (x: int32_t) thin abi("C") -> int32_t
def surf_inline_double(x: int32_t) raises -> int32_t

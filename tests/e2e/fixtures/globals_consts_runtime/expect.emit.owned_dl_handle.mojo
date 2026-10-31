# Each non-comment line must be present in the emitted file.
from std.simd import SIMD
from std.atomic import Atomic
comptime _BINDGEN_LIB_PATH_CANDIDATE: String
comptime _BINDGEN_LIB_PATH_ENV = "MOJO_BINDGEN_GLOBALS_CONSTS_RUNTIME_LIBRARY_PATH"
def _bindgen_append_dylib_candidate(mut paths: List[Path], path: String):
_bindgen_append_dylib_candidate(paths, _bindgen_env_path(_BINDGEN_LIB_PATH_ENV))
return OwnedDLHandle(path)
def _bindgen_dylib() -> Pointer[OwnedDLHandle, MutUntrackedOrigin]:
comptime int32_t = Int32
comptime gcr_vec4 = SIMD[DType.float32, 4]
comptime gcr_mut = GlobalVar[T=int32_t, link="gcr_mut"]
comptime gcr_limit = GlobalConst[T=int32_t, link="gcr_limit"]
comptime gcr_vec_const = GlobalConst[T=gcr_vec4, link="gcr_vec_const"]
comptime gcr_vec_mut = GlobalVar[T=gcr_vec4, link="gcr_vec_mut"]
# global variable gcr_atomic: Atomic[c_int] (atomic global requires manual binding (use Atomic APIs on a pointer))

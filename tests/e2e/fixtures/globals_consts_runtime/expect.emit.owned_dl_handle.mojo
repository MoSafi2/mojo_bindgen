# Each non-comment line must be present in the emitted file.
from std.builtin.simd import SIMD
from std.atomic import Atomic
comptime _BINDGEN_LIB_PATH: String
def _bindgen_dl() raises -> OwnedDLHandle:
comptime gcr_vec4 = SIMD[DType.float32, 4]
comptime gcr_mut = GlobalVar[T=Int32, link="gcr_mut"]
comptime gcr_limit = GlobalConst[T=Int32, link="gcr_limit"]
comptime gcr_vec_const = GlobalConst[T=gcr_vec4, link="gcr_vec_const"]
comptime gcr_vec_mut = GlobalVar[T=gcr_vec4, link="gcr_vec_mut"]
# global variable gcr_atomic: Atomic[DType.int32] (atomic global requires manual binding (use Atomic APIs on a pointer))

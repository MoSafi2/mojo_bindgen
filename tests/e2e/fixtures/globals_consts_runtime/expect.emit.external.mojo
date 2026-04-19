# Each non-comment line must be present in the emitted file.
from std.ffi import external_call, OwnedDLHandle, DEFAULT_RTLD
from std.builtin.simd import SIMD
from std.atomic import Atomic
struct GlobalVar[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:
struct GlobalConst[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:
comptime gcr_vec4 = SIMD[DType.float32, 4]
comptime gcr_mut = GlobalVar[T=Int32, link="gcr_mut"]
comptime gcr_limit = GlobalConst[T=Int32, link="gcr_limit"]
comptime gcr_vec_const = GlobalConst[T=gcr_vec4, link="gcr_vec_const"]
comptime gcr_vec_mut = GlobalVar[T=gcr_vec4, link="gcr_vec_mut"]
# global variable gcr_atomic: Atomic[DType.int32] (atomic global requires manual binding (use Atomic APIs on a pointer))

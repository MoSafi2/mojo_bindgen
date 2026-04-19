from globals_consts_runtime_bindings_dl import (
    gcr_limit,
    gcr_mut,
    gcr_vec4,
    gcr_vec_const,
    gcr_vec_mut,
)


def main() raises:
    print("gcr_limit|", gcr_limit.load())
    print("gcr_mut_before|", gcr_mut.load())
    gcr_mut.store(99)
    print("gcr_mut_after|", gcr_mut.load())

    var vc = gcr_vec_const.load()
    print("gcr_vec_const_lane0|", vc[0])
    print("gcr_vec_const_lane3|", vc[3])

    var vm = gcr_vec_mut.load()
    print("gcr_vec_mut_lane0_before|", vm[0])
    print("gcr_vec_mut_lane2_before|", vm[2])
    gcr_vec_mut.store(gcr_vec4(10.0, 20.0, 30.0, 40.0))
    var vm2 = gcr_vec_mut.load()
    print("gcr_vec_mut_lane0_after|", vm2[0])
    print("gcr_vec_mut_lane2_after|", vm2[2])

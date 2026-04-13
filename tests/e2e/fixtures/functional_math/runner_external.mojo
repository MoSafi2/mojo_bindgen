from functional_math_bindings_external import fm_add, fm_affine, fm_hash_step, fm_mix3


def main() raises:
    print("fm_add_case0|", fm_add(2, 40))
    print("fm_mix3_case0|", fm_mix3(3, 5, 3))
    print("fm_affine_case0|", fm_affine(1.5, 2.0, 0.25))
    print("fm_hash_step_case0|", fm_hash_step(1469598103934665603, 42))

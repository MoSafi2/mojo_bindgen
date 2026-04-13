from full_surface_runtime_bindings_external import (
    surf_add,
    surf_affine,
    surf_apply_mode,
    surf_flags_score,
    surf_global_plus,
    surf_is_nonzero,
    surf_matrix_trace,
    surf_packed_sum,
    surf_union_from_int,
)


def main() raises:
    print("surf_add|", surf_add(20, 22))
    print("surf_affine|", surf_affine(1.5, 3.0, -1.0))
    print("surf_apply_add|", surf_apply_mode(1, 9, 4))
    print("surf_apply_sub|", surf_apply_mode(2, 9, 4))
    print("surf_nonzero|", Int(surf_is_nonzero(-1)))
    print("surf_union|", surf_union_from_int(33))
    print("surf_flags|", surf_flags_score(1, 1, 3, 2))
    print("surf_packed|", surf_packed_sum(3, 10))
    print("surf_matrix_trace|", surf_matrix_trace(1.0, 2.0, 3.0, 4.0))
    print("surf_global_plus|", surf_global_plus(1))

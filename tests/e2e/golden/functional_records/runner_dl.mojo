from functional_records_bindings_dl import (
    fr_apply_mode,
    fr_is_nonzero,
    fr_linear,
)


def main() raises:
    print("fr_linear_case0|", fr_linear(6, 3, -4))
    print("fr_apply_add|", fr_apply_mode(1, 9, 5))
    print("fr_apply_sub|", fr_apply_mode(2, 9, 5))
    print("fr_nonzero_true|", Int(fr_is_nonzero(-7)))
    print("fr_nonzero_false|", Int(fr_is_nonzero(0)))

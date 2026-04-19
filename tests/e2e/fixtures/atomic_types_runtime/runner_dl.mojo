from p1_atomic_types_runtime_bindings_dl import (
    at_addr,
    at_addr_const,
    at_dec,
    at_get,
    at_inc,
    at_inc_ptr,
    at_load_ptr,
    at_reset,
    at_store_ptr,
)


def main() raises:
    at_reset(7)
    print("at_inc_case0|", at_inc())
    print("at_dec_case0|", at_dec())
    var p = at_addr()
    var cp = at_addr_const()
    print("at_ptr_load_case0|", at_load_ptr(cp))
    at_store_ptr(p, 41)
    print("at_ptr_load_case1|", at_load_ptr(cp))
    print("at_ptr_inc_case0|", at_inc_ptr(p))
    print("at_final_case0|", at_get())

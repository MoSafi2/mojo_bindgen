comptime int32_t = Int32
comptime pfr_binary_op_t = def (arg0: int32_t, arg1: int32_t) thin abi("C") -> int32_t
def pfr_select_add() -> pfr_binary_op_t:
_bindgen_function[def() thin abi("C") -> pfr_binary_op_t](StringSlice("pfr_select_add"))
def pfr_sanity(

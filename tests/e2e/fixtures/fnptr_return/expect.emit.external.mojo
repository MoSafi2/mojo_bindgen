external_call[
comptime int32_t = Int32
comptime pfr_binary_op_t = def (arg0: int32_t, arg1: int32_t) thin abi("C") -> int32_t
def pfr_select_add() abi("C") -> pfr_binary_op_t:
return external_call["pfr_select_add", pfr_binary_op_t]()
def pfr_sanity(

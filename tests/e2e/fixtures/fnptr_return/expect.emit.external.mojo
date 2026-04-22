external_call[
comptime int32_t = c_int
comptime pfr_binary_op_t = def (arg0: int32_t, arg1: int32_t) thin abi("C") -> int32_t
def pfr_select_add() abi("C") -> UnsafePointer[pfr_binary_op_t, MutExternalOrigin]:
return external_call["pfr_select_add", UnsafePointer[pfr_binary_op_t, MutExternalOrigin]]()
def pfr_sanity(

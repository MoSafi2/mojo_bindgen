comptime pfr_binary_op_t = def (arg0: c_int, arg1: c_int) thin abi("C") -> c_int
def pfr_select_add() raises -> UnsafePointer[pfr_binary_op_t, MutExternalOrigin]:
return _bindgen_dl().call["pfr_select_add", UnsafePointer[pfr_binary_op_t, MutExternalOrigin]]()
def pfr_sanity(

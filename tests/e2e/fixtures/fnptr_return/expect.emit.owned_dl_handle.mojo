comptime pfr_binary_op_t = def (arg0: Int32, arg1: Int32) abi("C") -> Int32
def pfr_select_add() raises -> UnsafePointer[pfr_binary_op_t, MutExternalOrigin]:
return _bindgen_dl().call["pfr_select_add", UnsafePointer[pfr_binary_op_t, MutExternalOrigin]]()
def pfr_sanity(

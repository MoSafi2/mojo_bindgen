external_call[
comptime pfr_binary_op_t = def (arg0: Int32, arg1: Int32) abi("C") -> Int32
def pfr_select_add() abi("C") -> UnsafePointer[pfr_binary_op_t, MutExternalOrigin]:
return external_call["pfr_select_add", MutOpaquePointer[MutExternalOrigin]]()
def pfr_sanity(

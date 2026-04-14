comptime pfr_binary_op_t = MutOpaquePointer[MutExternalOrigin]
def pfr_select_add() raises -> pfr_binary_op_t:
return _bindgen_dl().call["pfr_select_add", MutOpaquePointer[MutExternalOrigin]]()
def pfr_sanity(

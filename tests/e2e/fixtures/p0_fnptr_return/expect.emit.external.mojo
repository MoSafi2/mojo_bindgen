external_call[
comptime pfr_binary_op_t = MutOpaquePointer[MutExternalOrigin]
def pfr_select_add() abi("C") -> pfr_binary_op_t:
return external_call["pfr_select_add", MutOpaquePointer[MutExternalOrigin]]()
def pfr_sanity(

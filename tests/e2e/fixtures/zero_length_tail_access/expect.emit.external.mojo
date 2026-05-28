external_call[
struct zta_packet
var payload: InlineArray[uint8_t, 0]
@staticmethod
def payload_offset() -> UInt:
def payload_ptr(base: UnsafePointer[zta_packet, ImmutExternalOrigin]) -> UnsafePointer[uint8_t, ImmutExternalOrigin]:
def payload_mut_ptr(base: UnsafePointer[zta_packet, MutExternalOrigin]) -> UnsafePointer[uint8_t, MutExternalOrigin]:
def zta_fixture(
def zta_header_size(
def zta_sanity(

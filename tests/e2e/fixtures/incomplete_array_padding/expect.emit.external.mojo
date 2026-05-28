external_call[
struct iap_packet
var payload: InlineArray[uint8_t, 0]
@staticmethod
def payload_offset() -> UInt:
def payload_ptr(base: UnsafePointer[iap_packet, ImmutExternalOrigin]) -> UnsafePointer[uint8_t, ImmutExternalOrigin]:
def payload_mut_ptr(base: UnsafePointer[iap_packet, MutExternalOrigin]) -> UnsafePointer[uint8_t, MutExternalOrigin]:
def iap_fixture(
def iap_header_size(
def iap_sanity(

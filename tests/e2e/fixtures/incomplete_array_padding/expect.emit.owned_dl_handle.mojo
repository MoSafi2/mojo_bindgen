struct iap_packet
var payload: InlineArray[uint8_t, 0]
@staticmethod
def payload_offset() -> UInt:
def payload_ptr(base: UnsafePointer[iap_packet, ImmutUntrackedOrigin]) -> UnsafePointer[uint8_t, ImmutUntrackedOrigin]:
def payload_mut_ptr(base: UnsafePointer[iap_packet, MutUntrackedOrigin]) -> UnsafePointer[uint8_t, MutUntrackedOrigin]:
def iap_fixture(
def iap_header_size(
def iap_sanity(

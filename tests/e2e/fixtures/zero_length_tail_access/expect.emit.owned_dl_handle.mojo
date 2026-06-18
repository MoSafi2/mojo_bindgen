struct zta_packet
var payload: InlineArray[uint8_t, 0]
@staticmethod
def payload_offset() -> UInt:
def payload_ptr(base: UnsafePointer[zta_packet, ImmutUntrackedOrigin]) -> UnsafePointer[uint8_t, ImmutUntrackedOrigin]:
def payload_mut_ptr(base: UnsafePointer[zta_packet, MutUntrackedOrigin]) -> UnsafePointer[uint8_t, MutUntrackedOrigin]:
def zta_fixture(
def zta_header_size(
def zta_sanity(

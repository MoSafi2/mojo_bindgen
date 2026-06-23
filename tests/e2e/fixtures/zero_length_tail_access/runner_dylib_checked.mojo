import zero_length_tail_access_bindings_dylib_checked as bindings


def main() raises:
    print("zta_header_size|", bindings.zta_header_size())
    print("zta_sanity|", bindings.zta_sanity(40))
    var packet = bindings.zta_fixture()
    if not packet:
        raise Error(String("missing zta_fixture"))
    var packet_ptr = packet.value()
    print("zta_payload_offset|", bindings.zta_packet.payload_offset())
    _ = bindings.zta_packet.payload_ptr(packet_ptr)

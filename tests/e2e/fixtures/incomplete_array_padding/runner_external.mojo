import incomplete_array_padding_bindings_external as bindings


def main() raises:
    print("iap_header_size|", bindings.iap_header_size())
    print("iap_sanity|", bindings.iap_sanity(38))
    var packet = bindings.iap_fixture()
    if not packet:
        raise Error(String("missing iap_fixture"))
    var packet_ptr = packet.value()
    print("iap_payload_offset|", bindings.iap_packet.payload_offset())
    _ = bindings.iap_packet.payload_ptr(packet_ptr)

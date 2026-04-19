from p0_incomplete_array_padding_bindings_external import iap_header_size, iap_sanity


def main() raises:
    print("iap_header_size|", iap_header_size())
    print("iap_sanity|", iap_sanity(38))

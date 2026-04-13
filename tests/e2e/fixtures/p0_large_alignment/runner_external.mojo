from p0_large_alignment_bindings_external import la_align, la_offset_b, la_sanity


def main() raises:
    print("la_align|", la_align())
    print("la_offset_b|", la_offset_b())
    print("la_sanity|", la_sanity(26))

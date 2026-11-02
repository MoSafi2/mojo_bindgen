from const_array_decay_bindings_external import cad_sanity, cad_values, cad_sum4


def main() raises:
    print("cad_sanity|", cad_sanity())
    if cad_sum4(cad_values()) != 10:
        raise Error("C array parameter decay failed")

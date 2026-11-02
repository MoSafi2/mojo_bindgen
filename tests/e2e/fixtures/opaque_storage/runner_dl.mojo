from std.sys.info import size_of, align_of
import opaque_storage_bindings_dl as bindings


def main() raises:
    var first = bindings.extended_fixture()
    if not first:
        raise Error("missing extended fixture")
    var second = first.value().unsafe_offset(1)
    bindings.extended_set(second)
    print("value|", bindings.extended_check(second))
    print("guard|", bindings.extended_guard())
    print("size|", size_of[bindings.Extended]())
    print("align|", align_of[bindings.Extended]())
    print("array_size|", size_of[Array[bindings.Extended, 2]]())
    print("c_size|", bindings.extended_size())
    print("c_align|", bindings.extended_align())
    print("c_stride|", bindings.extended_stride())
    if size_of[bindings.ExtendedUnion]() != Int(bindings.extended_union_size()) or align_of[
        bindings.ExtendedUnion
    ]() != Int(bindings.extended_union_align()):
        raise Error("opaque union geometry mismatch")

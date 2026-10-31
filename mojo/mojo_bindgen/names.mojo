"""Identifier normalization matching the Python implementation's Unicode policy."""

from ._unicode import is_alnum, is_digit, is_space


def mojo_ident(name: String, fallback: String = "field") -> String:
    var blank = True
    for cp in name.codepoints():
        if not is_space(Int(cp)):
            blank = False
            break
    if blank:
        return fallback.copy()
    var result = String()
    var first = True
    for cp in name.codepoints():
        var code = Int(cp)
        var digit = cp.is_ascii_digit() if cp.is_ascii() else is_digit(code)
        var alnum = (
            cp.is_ascii_lower() or cp.is_ascii_upper() or digit if cp.is_ascii() else is_alnum(code)
        )
        if first and digit:
            result += "_"
        result += String(cp) if alnum or code == 95 else "_"
        first = False
    comptime reserved = " def struct fn var let inout out mut ref copy owned deinit self Self import from as pass return raise raises try except finally with if elif else for while break continue and or not is in del alias comptime True False None imm read thin abi match case where std "
    if String(" " + result + " ") in reserved:
        result += "_"
    return result^


def normalized_name(name: String) -> String:
    # Python's mapper strips surrounding Unicode whitespace before normalizing.
    var points = List[Int]()
    for cp in name.codepoints():
        points.append(Int(cp))
    var start = 0
    var end = len(points)
    while start < end and is_space(points[start]):
        start += 1
    while end > start and is_space(points[end - 1]):
        end -= 1
    var stripped = String()
    from std.collections.string import chr

    for i in range(start, end):
        stripped += chr(points[i])
    return mojo_ident(stripped)

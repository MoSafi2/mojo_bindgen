"""Identifier normalization matching the Python implementation's Unicode policy."""

from std.collections.string import chr
from .._unicode import is_alnum, is_digit, is_space, is_printable


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

    for i in range(start, end):
        stripped += chr(points[i])
    return mojo_ident(stripped)


def quoted(value: String) -> String:
    var quote = String("'" if '"' in value or "'" not in value else '"')
    var out = quote.copy()
    for cp in value.codepoints():
        var text = String(cp)
        if text == quote or text == "\\":
            out += "\\" + text
        elif Int(cp) == 10:
            out += "\\n"
        elif Int(cp) == 13:
            out += "\\r"
        elif Int(cp) == 9:
            out += "\\t"
        elif not is_printable(Int(cp)):
            var code = Int(cp)
            var width = 2 if code < 256 else (4 if code < 65536 else 8)
            out += "\\x" if width == 2 else (String("\\u") if width == 4 else String("\\U"))
            comptime hex = "0123456789abcdef"
            for shift in range(width - 1, -1, -1):
                out += String(hex[byte=(code >> (shift * 4)) & 15])
        else:
            out += text
    return out + quote


def strip_whitespace(value: String) -> String:
    var points = List[Int]()
    for cp in value.codepoints():
        points.append(Int(cp))
    var start = 0
    var end = len(points)
    while start < end and is_space(points[start]):
        start += 1
    while end > start and is_space(points[end - 1]):
        end -= 1
    var out = String()
    for i in range(start, end):
        out += chr(points[i])
    return out^


def mojo_float_literal_text(value: String) -> String:
    var trimmed = _rstrip_whitespace(value)
    var bytes = trimmed.as_bytes()
    var end = len(bytes)
    while end and (
        bytes[end - 1] == 102
        or bytes[end - 1] == 70
        or bytes[end - 1] == 108
        or bytes[end - 1] == 76
    ):
        end -= 1
    return String(trimmed[byte=0:end])


def mojo_align_decorator_ok(align: Int) -> Bool:
    return align > 1 and align <= (1 << 29) and (align & (align - 1)) == 0


def sort_strings(mut values: List[String]):
    sort(Span(values))


def _rstrip_whitespace(value: String) -> String:
    var points = List[Int]()
    for cp in value.codepoints():
        points.append(Int(cp))
    var end = len(points)
    while end and is_space(points[end - 1]):
        end -= 1
    var result = String()
    for i in range(end):
        result += chr(points[i])
    return result^

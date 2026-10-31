"""Exact literal values and binary64 text compatibility; geometry uses machine Int."""

from std.collections.string import chr
from std.utils.numerics import isinf, isnan


struct IntegerValue(Copyable, Equatable, Movable):
    var digits: String

    @implicit
    def __init__(out self, value: Int):
        self.digits = String(value)

    @staticmethod
    def from_decimal(text: String) raises -> Self:
        var bytes = text.as_bytes()
        var start = 0
        var negative = False
        if len(bytes) and bytes[0] == 45:
            start = 1
            negative = True
        if start == len(bytes):
            raise Error("expected integer digits")
        for i in range(start, len(bytes)):
            if bytes[i] < 48 or bytes[i] > 57:
                raise Error("expected integer digits")
        while start < len(bytes) - 1 and bytes[start] == 48:
            start += 1
        var result = Self(0)
        result.digits = String(
            "-" if negative and not (start == len(bytes) - 1 and bytes[start] == 48) else ""
        )
        for i in range(start, len(bytes)):
            result.digits += chr(Int(bytes[i]))
        return result^

    def to_int(self) raises -> Int:
        return Int(self.digits)

    def __eq__(self, other: Self) -> Bool:
        return self.digits == other.digits


def parse_float(text: String) raises -> Float64:
    from .analysis.common import strip_whitespace, quoted

    var stripped = strip_whitespace(text)
    var bytes = stripped.as_bytes()
    var normalized = String()
    var valid = True
    for i in range(len(bytes)):
        if bytes[i] == 95:
            if i == 0 or i + 1 == len(bytes):
                valid = False
            elif bytes[i - 1] < 48 or bytes[i - 1] > 57 or bytes[i + 1] < 48 or bytes[i + 1] > 57:
                valid = False
        else:
            normalized += chr(Int(bytes[i]))
    if valid:
        try:
            return Float64(normalized)
        except:
            pass
    raise Error("could not convert string to float: " + quoted(text))


def float_text(value: Float64) -> String:
    if isnan(value):
        return String("nan")
    if isinf(value):
        return String("-inf" if value < 0 else "inf")
    return String(value)


def mask_text(width: Int) -> String:
    if width <= 0:
        return String("0x0")
    comptime digits = "0123456789abcdef"
    var result = String("0x")
    if width % 4:
        result += String(digits[byte=(1 << (width % 4)) - 1])
    for _ in range(width // 4):
        result += "f"
    return result^


def sign_bit_text(width: Int) -> String:
    if width <= 0:
        return String("0x0")
    comptime digits = "1248"
    var result = String("0x") + String(digits[byte=(width - 1) % 4])
    for _ in range((width - 1) // 4):
        result += "0"
    return result^


def parse_hex_float(text: String) raises -> Float64:
    from std.ffi import external_call
    from std.memory import Pointer

    var end: Optional[Pointer[UInt8, MutUntrackedOrigin]] = {}
    # String.unsafe_ptr() promises UTF-8 bytes, not a C terminator.
    var terminated = text + "\0"
    var value = external_call["strtod", Float64](terminated.unsafe_ptr(), Pointer(to=end))
    if "\0" in text or not end or end.value()[unsafe_offset=0] != 0:
        raise Error("invalid hexadecimal floating-point string")
    if isinf(value):
        raise Error("hexadecimal value too large to represent as a float")
    return value

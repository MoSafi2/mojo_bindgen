"""Pass-local signed-magnitude arithmetic for runtime C constant folding."""
from ..._numbers import IntegerValue


struct BigInteger(Copyable, Movable):
    var negative: Bool
    var words: List[UInt32]

    def __init__(out self, negative: Bool = False, var words: List[UInt32] = []):
        self.negative = negative
        self.words = words^
        self.trim()

    def trim(mut self):
        while len(self.words) and self.words[len(self.words) - 1] == 0:
            _ = self.words.pop()
        if not len(self.words):
            self.negative = False

    @staticmethod
    def parse(text: String, base: Int = 10) raises -> Self:
        var result = Self()
        var start = 0
        var negative = False
        var bytes = text.as_bytes()
        if len(bytes) and (bytes[0] == 45 or bytes[0] == 43):
            negative = bytes[0] == 45
            start = 1
        if start == len(bytes):
            raise Error("expected integer digits")
        for i in range(start, len(bytes)):
            var digit = Int(bytes[i]) - 48
            if bytes[i] >= 65 and bytes[i] <= 70:
                digit = Int(bytes[i]) - 55
            elif bytes[i] >= 97 and bytes[i] <= 102:
                digit = Int(bytes[i]) - 87
            if digit < 0 or digit >= base:
                raise Error("invalid integer digit")
            var carry = UInt64(digit)
            for j in range(len(result.words)):
                var value = UInt64(result.words[j]) * UInt64(base) + carry
                result.words[j] = UInt32(value)
                carry = value >> 32
            if carry:
                result.words.append(UInt32(carry))
        result.negative = negative and len(result.words) > 0
        return result^

    def value(self) raises -> IntegerValue:
        from std.collections.string import chr

        var words = self.words.copy()
        var reverse = List[Int]()
        while len(words):
            var carry = UInt64(0)
            for reverse_index in range(len(words)):
                var i = len(words) - 1 - reverse_index
                var value = (carry << 32) | UInt64(words[i])
                words[i] = UInt32(value // 10)
                carry = value % 10
            reverse.append(Int(carry))
            while len(words) and words[len(words) - 1] == 0:
                _ = words.pop()
        var text = String("-" if self.negative else "")
        if not len(reverse):
            text += "0"
        for i in range(len(reverse)):
            text += chr(48 + reverse[len(reverse) - 1 - i])
        return IntegerValue.from_decimal(text)


def magnitude_compare(a: BigInteger, b: BigInteger) -> Int:
    if len(a.words) != len(b.words):
        return 1 if len(a.words) > len(b.words) else -1
    for j in range(len(a.words)):
        var i = len(a.words) - 1 - j
        if a.words[i] != b.words[i]:
            return 1 if a.words[i] > b.words[i] else -1
    return 0


def magnitude_add(a: BigInteger, b: BigInteger) -> BigInteger:
    var words = List[UInt32]()
    var carry = UInt64(0)
    for i in range(max(len(a.words), len(b.words))):
        var value = carry
        if i < len(a.words):
            value += UInt64(a.words[i])
        if i < len(b.words):
            value += UInt64(b.words[i])
        words.append(UInt32(value))
        carry = value >> 32
    if carry:
        words.append(UInt32(carry))
    return BigInteger(False, words^)


def magnitude_subtract(a: BigInteger, b: BigInteger) -> BigInteger:
    var words = List[UInt32]()
    var borrow = UInt64(0)
    for i in range(len(a.words)):
        var sub = borrow
        if i < len(b.words):
            sub += UInt64(b.words[i])
        var value = UInt64(a.words[i])
        words.append(UInt32(value - sub))
        borrow = UInt64(value < sub)
    return BigInteger(False, words^)


def add(a: BigInteger, b: BigInteger) -> BigInteger:
    var result: BigInteger
    if a.negative == b.negative:
        result = magnitude_add(a, b)
        result.negative = a.negative
    elif magnitude_compare(a, b) >= 0:
        result = magnitude_subtract(a, b)
        result.negative = a.negative
    else:
        result = magnitude_subtract(b, a)
        result.negative = b.negative
    result.trim()
    return result^


def negate(a: BigInteger) -> BigInteger:
    return BigInteger(not a.negative, a.words.copy())


def multiply(a: BigInteger, b: BigInteger) -> BigInteger:
    var result = BigInteger()
    result.words = List[UInt32](length=len(a.words) + len(b.words), fill=0)
    for i in range(len(a.words)):
        var carry = UInt64(0)
        for j in range(len(b.words)):
            var value = (
                UInt64(a.words[i]) * UInt64(b.words[j]) + UInt64(result.words[i + j]) + carry
            )
            result.words[i + j] = UInt32(value)
            carry = value >> 32
        result.words[i + len(b.words)] = UInt32(carry)
    result.negative = a.negative != b.negative
    result.trim()
    return result^


def shift_left(a: BigInteger, n: Int) -> BigInteger:
    var words = List[UInt32](length=n // 32, fill=0)
    var carry = UInt64(0)
    for word in a.words:
        var value = (UInt64(word) << UInt64(n % 32)) | carry
        words.append(UInt32(value))
        carry = value >> 32
    if carry:
        words.append(UInt32(carry))
    return BigInteger(a.negative, words^)


def magnitude_divmod(a: BigInteger, b: BigInteger) -> Tuple[BigInteger, BigInteger]:
    var quotient = BigInteger()
    var remainder = BigInteger()
    quotient.words = List[UInt32](length=len(a.words), fill=0)
    for reverse_index in range(len(a.words) * 32):
        var bit = len(a.words) * 32 - 1 - reverse_index
        remainder = shift_left(remainder, 1)
        if (a.words[bit // 32] >> UInt32(bit % 32)) & 1:
            if not len(remainder.words):
                remainder.words.append(1)
            else:
                remainder.words[0] |= 1
        if magnitude_compare(remainder, b) >= 0:
            remainder = magnitude_subtract(remainder, b)
            quotient.words[bit // 32] |= UInt32(1) << UInt32(bit % 32)
    quotient.trim()
    return (quotient^, remainder^)


def twos(a: BigInteger, count: Int) -> List[UInt32]:
    var words = List[UInt32](length=count, fill=0)
    for i in range(len(a.words)):
        words[i] = a.words[i]
    if a.negative:
        var carry = UInt64(1)
        for i in range(count):
            var value = UInt64(~words[i]) + carry
            words[i] = UInt32(value)
            carry = value >> 32
    return words^


def bitwise(op: String, a: BigInteger, b: BigInteger) -> BigInteger:
    var count = max(len(a.words), len(b.words)) + 1
    var lhs = twos(a, count)
    var rhs = twos(b, count)
    for i in range(count):
        if op == "&":
            lhs[i] &= rhs[i]
        elif op == "|":
            lhs[i] |= rhs[i]
        else:
            lhs[i] ^= rhs[i]
    var negative = Bool(lhs[count - 1] >> 31)
    if negative:
        var carry = UInt64(1)
        for i in range(count):
            var value = UInt64(~lhs[i]) + carry
            lhs[i] = UInt32(value)
            carry = value >> 32
    return BigInteger(negative, lhs^)


def unary(op: String, value: IntegerValue) raises -> IntegerValue:
    var a = BigInteger.parse(value.digits)
    if op == "-":
        return negate(a).value()
    if op == "~":
        return add(negate(a), BigInteger(True, [1])).value()
    if op == "!":
        return IntegerValue(Int(not len(a.words)))
    return value.copy()


def binary(op: String, lhs: IntegerValue, rhs: IntegerValue) raises -> Optional[IntegerValue]:
    var a = BigInteger.parse(lhs.digits)
    var b = BigInteger.parse(rhs.digits)
    var comparison = magnitude_compare(a, b)
    if a.negative != b.negative:
        comparison = -1 if a.negative else 1
    elif a.negative:
        comparison = -comparison
    if op == "+":
        return add(a, b).value()
    if op == "-":
        return add(a, negate(b)).value()
    if op == "*":
        return multiply(a, b).value()
    if op == "/" or op == "%":
        if not len(b.words):
            return None
        var division = magnitude_divmod(a, b)
        var quotient = division[0].copy()
        var remainder = division[1].copy()
        quotient.negative = (a.negative != b.negative) and len(quotient.words) > 0
        remainder.negative = a.negative and len(remainder.words) > 0
        if op == "/":
            return quotient.value()
        if len(remainder.words) and a.negative != b.negative:
            remainder = add(remainder, b)
        return remainder.value()
    if op == "<<" or op == ">>":
        if b.negative:
            return None
        var n = rhs.to_int()
        if op == "<<":
            return shift_left(a, n).value()
        if n >= len(a.words) * 32:
            return IntegerValue(-1 if a.negative else 0)
        var divisor = shift_left(BigInteger(False, [1]), n)
        var division = magnitude_divmod(a, divisor)
        var quotient = division[0].copy()
        var remainder = division[1].copy()
        quotient.negative = a.negative
        if a.negative and len(remainder.words):
            quotient = add(quotient, BigInteger(True, [1]))
        return quotient.value()
    if op == "&" or op == "|" or op == "^":
        return bitwise(op, a, b).value()
    if op == "<":
        return IntegerValue(Int(comparison < 0))
    if op == "<=":
        return IntegerValue(Int(comparison <= 0))
    if op == ">":
        return IntegerValue(Int(comparison > 0))
    if op == ">=":
        return IntegerValue(Int(comparison >= 0))
    if op == "==":
        return IntegerValue(Int(comparison == 0))
    if op == "!=":
        return IntegerValue(Int(comparison != 0))
    if op == "&&":
        return IntegerValue(Int(len(a.words) > 0 and len(b.words) > 0))
    if op == "||":
        return IntegerValue(Int(len(a.words) > 0 or len(b.words) > 0))
    return None

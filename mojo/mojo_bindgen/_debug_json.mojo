"""Strict JSON primitives used by the type debug codec (integer numbers only)."""

from std.collections.string import chr
from std.memory import ArcPointer
from ._numbers import IntegerValue, float_text, parse_float
from std.utils.numerics import isnan, isinf


__enum JSON(Copyable, Movable):
    case null
    case boolean(Bool)
    case integer(IntegerValue)
    case floating(Float64)
    case string(String)
    case array(List[ArcPointer[JSON]])
    case object(Dict[String, ArcPointer[JSON]])

    def __deinit__(deinit self):
        pass

    def text(self) raises -> String:
        match self:
            case .string(s):
                return s.copy()
            case _:
                raise Error("expected JSON string")

    def int_value(self) raises -> Int:
        match self:
            case .integer(v):
                return v.to_int()
            case _:
                raise Error("expected JSON integer")

    def integer_value(self) raises -> IntegerValue:
        match self:
            case .integer(v):
                return v.copy()
            case _:
                raise Error("expected JSON integer")

    def float_value(self) raises -> Float64:
        match self:
            case .floating(v):
                return v
            case .integer(v):
                var result = parse_float(v.digits)
                if isinf(result):
                    raise Error("int too large to convert to float")
                return result
            case _:
                raise Error("expected JSON number")

    def bool_value(self) raises -> Bool:
        match self:
            case .boolean(v):
                return v
            case _:
                raise Error("expected JSON boolean")

    def is_null(self) -> Bool:
        match self:
            case .null:
                return True
            case _:
                return False

    def items(self) raises -> List[ArcPointer[JSON]]:
        match self:
            case .array(v):
                return v.copy()
            case _:
                raise Error("expected JSON array")

    def get(self, key: String) raises -> ArcPointer[JSON]:
        match self:
            case .object(v):
                if key not in v:
                    raise Error("missing field: " + key)
                return v[key].copy()
            case _:
                raise Error("expected JSON object")

    def has(self, key: String) raises -> Bool:
        match self:
            case .object(v):
                return key in v
            case _:
                raise Error("expected JSON object")

    def check_fields(self, allowed: String) raises:
        match self:
            case .object(v):
                for key in v:
                    var found = False
                    for candidate in allowed.split("|"):
                        if candidate.byte_length() != 0 and key == candidate:
                            found = True
                    if not found:
                        raise Error("unknown field: " + key)
            case _:
                raise Error("expected JSON object")


def quote(text: String) -> String:
    var result = String('"')
    for cp in text.codepoints():
        var value = Int(cp)
        if value == 34:
            result += '\\"'
        elif value == 92:
            result += "\\\\"
        elif value < 32:
            comptime hex = "0123456789abcdef"
            result += "\\u00" + String(hex[byte=value // 16]) + String(hex[byte=value % 16])
        else:
            result += String(cp)
    result += '"'
    return result^


def dump_json(value: JSON) -> String:
    match value:
        case .null:
            return String("null")
        case .boolean(v):
            return String("true" if v else "false")
        case .integer(v):
            return v.digits.copy()
        case .floating(v):
            if isnan(v):
                return String("NaN")
            if isinf(v):
                return String("-Infinity" if v < 0 else "Infinity")
            return float_text(v)
        case .string(v):
            return quote(v)
        case .array(v):
            var out = String("[")
            for i in range(len(v)):
                if i:
                    out += ","
                out += dump_json(v[i].ptr()[])
            return out + "]"
        case .object(v):
            var out = String("{")
            var first = True
            for entry in v.items():
                if not first:
                    out += ","
                first = False
                out += quote(entry.key) + ":" + dump_json(entry.value.ptr()[])
            return out + "}"


struct _Parser(Movable):
    var points: List[Int]
    var pos: Int

    def __init__(out self, text: String):
        self.points = List[Int]()
        for cp in text.codepoints():
            self.points.append(Int(cp))
        self.pos = 0

    def _peek(self) -> Int:
        return self.points[self.pos] if self.pos < len(self.points) else -1

    def _space(mut self):
        while self._peek() == 32 or self._peek() == 9 or self._peek() == 10 or self._peek() == 13:
            self.pos += 1

    def _take(mut self, code: Int) raises:
        if self._peek() != code:
            raise Error("invalid JSON at codepoint " + String(self.pos))
        self.pos += 1

    def _hex4(mut self) raises -> Int:
        var value = 0
        for _ in range(4):
            var ch = self._peek()
            var digit: Int
            if ch >= 48 and ch <= 57:
                digit = ch - 48
            elif ch >= 65 and ch <= 70:
                digit = ch - 55
            elif ch >= 97 and ch <= 102:
                digit = ch - 87
            else:
                raise Error("invalid JSON Unicode escape")
            value = value * 16 + digit
            self.pos += 1
        return value

    def _string(mut self) raises -> String:
        self._take(34)
        var result = String()
        while self._peek() != 34:
            var ch = self._peek()
            self.pos += 1
            if ch < 32:
                raise Error("unterminated or invalid JSON string")
            if ch != 92:
                result += chr(ch)
                continue
            ch = self._peek()
            self.pos += 1
            match ch:
                case 34 | 92 | 47:
                    result += chr(ch)
                case 98:
                    result += "\b"
                case 102:
                    result += "\f"
                case 110:
                    result += "\n"
                case 114:
                    result += "\r"
                case 116:
                    result += "\t"
                case 117:
                    var code = self._hex4()
                    if code >= 0xD800 and code <= 0xDBFF:
                        self._take(92)
                        self._take(117)
                        var low = self._hex4()
                        if low < 0xDC00 or low > 0xDFFF:
                            raise Error("invalid JSON surrogate pair")
                        code = 0x10000 + (code - 0xD800) * 1024 + low - 0xDC00
                    elif code >= 0xDC00 and code <= 0xDFFF:
                        raise Error("unpaired JSON surrogate")
                    result += chr(code)
                case _:
                    raise Error("invalid JSON escape")
        self._take(34)
        return result^

    def value(mut self, depth: Int = 0) raises -> JSON:
        if depth > 512:
            raise Error("JSON nesting limit exceeded")
        self._space()
        var ch = self._peek()
        if ch == 34:
            return JSON.string(self._string())
        if ch == 123:
            self.pos += 1
            self._space()
            var fields = Dict[String, ArcPointer[JSON]]()
            if self._peek() != 125:
                while True:
                    var key = self._string()
                    if key in fields:
                        raise Error("duplicate JSON key: " + key)
                    self._space()
                    self._take(58)
                    fields[key] = ArcPointer(self.value(depth + 1))
                    self._space()
                    if self._peek() != 44:
                        break
                    self.pos += 1
                    self._space()
            self._take(125)
            return JSON.object(fields^)
        if ch == 91:
            self.pos += 1
            self._space()
            var values = List[ArcPointer[JSON]]()
            if self._peek() != 93:
                while True:
                    values.append(ArcPointer(self.value(depth + 1)))
                    self._space()
                    if self._peek() != 44:
                        break
                    self.pos += 1
            self._take(93)
            return JSON.array(values^)
        if ch == 116:
            for c in "true".codepoints():
                self._take(Int(c))
            return JSON.boolean(True)
        if ch == 102:
            for c in "false".codepoints():
                self._take(Int(c))
            return JSON.boolean(False)
        if ch == 110:
            for c in "null".codepoints():
                self._take(Int(c))
            return materialize[JSON.null]()
        var number = String()
        if ch == 45:
            number += "-"
            self.pos += 1
        if self._peek() == 73:
            for c in "Infinity".codepoints():
                self._take(Int(c))
            return JSON.floating(parse_float(number + "inf"))
        if self._peek() == 78 and number.byte_length() == 0:
            for c in "NaN".codepoints():
                self._take(Int(c))
            return JSON.floating(parse_float("nan"))
        ch = self._peek()
        if ch < 48 or ch > 57:
            raise Error("expected JSON number")
        if ch == 48:
            number += "0"
            self.pos += 1
        else:
            while self._peek() >= 48 and self._peek() <= 57:
                number += chr(self._peek())
                self.pos += 1
        var floating = False
        if self._peek() == 46:
            floating = True
            number += "."
            self.pos += 1
            if self._peek() < 48 or self._peek() > 57:
                raise Error("expected fraction digits")
            while self._peek() >= 48 and self._peek() <= 57:
                number += chr(self._peek())
                self.pos += 1
        if self._peek() == 101 or self._peek() == 69:
            floating = True
            number += "e"
            self.pos += 1
            if self._peek() == 43 or self._peek() == 45:
                number += chr(self._peek())
                self.pos += 1
            if self._peek() < 48 or self._peek() > 57:
                raise Error("expected exponent digits")
            while self._peek() >= 48 and self._peek() <= 57:
                number += chr(self._peek())
                self.pos += 1
        if floating:
            return JSON.floating(parse_float(number))
        return JSON.integer(IntegerValue.from_decimal(number))


def parse_json(text: String) raises -> JSON:
    var parser = _Parser(text)
    var result = parser.value()
    parser._space()
    if parser.pos != len(parser.points):
        raise Error("trailing JSON input")
    return result^


def node(kind: String, var fields: Dict[String, ArcPointer[JSON]]) -> JSON:
    var value = Dict[String, ArcPointer[JSON]]()
    value["kind"] = ArcPointer(JSON.string(kind.copy()))
    value["fields"] = ArcPointer(JSON.object(fields^))
    return JSON.object(value^)

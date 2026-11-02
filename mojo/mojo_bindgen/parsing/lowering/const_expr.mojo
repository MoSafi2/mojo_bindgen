"""Token-based C constant parsing and exact integer folding."""
from std.memory import ArcPointer
from std.collections.string import chr
from ...ir import (
    CType,
    CConstExpr,
    CBinaryExpr,
    CUnaryExpr,
    CCastExpr,
    CSizeOfExpr,
    CFloatLiteral,
    IntLiteral,
    CharLiteral,
    StringLiteral,
    CNullPtrLiteral,
    CRefExpr,
    VoidType,
    IntType,
    IntKind,
    FloatType,
    FloatKind,
)
from ..._numbers import IntegerValue, parse_float, parse_hex_float
from .literal_resolver import LiteralResolver
from ..target_abi import probe_target_abi
from ...ir import TargetABI
from .primitive import default_int
from ._integer import BigInteger, unary, binary


struct ParsedConstExpr(Copyable, Movable):
    var expr: CConstExpr
    var primitive: Optional[CType]
    var diagnostic: Optional[String]

    def __init__(
        out self,
        var expr: CConstExpr,
        var primitive: Optional[CType],
        var diagnostic: Optional[String] = {},
    ):
        self.expr = expr^
        self.primitive = primitive^
        self.diagnostic = diagnostic^


def identifier(text: String) -> Bool:
    var bytes = text.as_bytes()
    if not len(bytes):
        return False
    for i in range(len(bytes)):
        var b = bytes[i]
        if (b >= 65 and b <= 90) or (b >= 97 and b <= 122) or b == 95:
            continue
        if i > 0 and b >= 48 and b <= 57:
            continue
        return False
    return True


def predefined(name: String) -> Bool:
    var names: List[String] = [
        "__FILE__",
        "__LINE__",
        "__DATE__",
        "__TIME__",
        "__STDC__",
        "__STDC_VERSION__",
        "__STDC_HOSTED__",
        "__STDC_IEC_559__",
        "__STDC_IEC_559_COMPLEX__",
        "__STDC_ISO_10646__",
        "__STDC_MB_MIGHT_NEQ_WC__",
        "__STDC_ANALYZABLE__",
        "__STDC_LIB_EXT1__",
        "__STDC_ALLOC_LIB__",
        "__COUNTER__",
    ]
    return (
        name in names
        or name.startswith("__STDC_NO_")
        or name.startswith("__STDC_IEC_60559_")
        or (name.startswith("__STDC_VERSION_") and name.endswith("_H__"))
    )


def looks_function_like(body: List[String]) -> Bool:
    if not len(body) or body[0] != "(":
        return False
    for i in range(1, len(body)):
        if body[i] == ")":
            return True
        if not identifier(body[i]) and body[i] != "," and body[i] != "...":
            return False
    return False


def precedence(op: String) -> Int:
    if op == "||":
        return 1
    if op == "&&":
        return 2
    if op == "|":
        return 3
    if op == "^":
        return 4
    if op == "&":
        return 5
    if op == "==" or op == "!=":
        return 6
    if op == "<" or op == "<=" or op == ">" or op == ">=":
        return 7
    if op == "<<" or op == ">>":
        return 8
    if op == "+" or op == "-":
        return 9
    if op == "*" or op == "/" or op == "%":
        return 10
    return -1


def decode_escapes(text: String) raises -> String:
    var points = List[Int]()
    for point in text.codepoints():
        points.append(Int(point))
    var result = String()
    var i = 0
    while i < len(points):
        var point = points[i]
        i += 1
        if point != 92 or i == len(points):
            result += chr(point)
            continue
        var esc = points[i]
        i += 1
        var simple: Dict[Int, Int] = {
            97: 7,
            98: 8,
            102: 12,
            110: 10,
            114: 13,
            116: 9,
            118: 11,
            92: 92,
            39: 39,
            34: 34,
            63: 63,
        }
        if esc in simple:
            result += chr(simple[esc])
        elif esc >= 48 and esc <= 55:
            var value = esc - 48
            var count = 1
            while i < len(points) and count < 3 and points[i] >= 48 and points[i] <= 55:
                value = value * 8 + points[i] - 48
                i += 1
                count += 1
            result += chr(value)
        elif esc == 120:
            var digits = String()
            while i < len(points):
                var ch = points[i]
                if not (
                    (ch >= 48 and ch <= 57) or (ch >= 65 and ch <= 70) or (ch >= 97 and ch <= 102)
                ):
                    break
                digits += chr(ch)
                i += 1
            if digits:
                result += chr(BigInteger.parse(digits, 16).value().to_int())
            else:
                result += "\\x"
        else:
            result += chr(esc)
    return result^


def fold(expr: CConstExpr) raises -> CConstExpr:
    match expr:
        case .c_unary_expr(v):
            var inner = fold(v.operand.ptr()[])
            match inner:
                case .int_literal(value):
                    return CConstExpr.int_literal(IntLiteral(unary(v.op, value.value)))
                case _:
                    return CConstExpr.c_unary_expr(CUnaryExpr(v.op.copy(), ArcPointer(inner^)))
        case .c_binary_expr(v):
            var lhs = fold(v.lhs.ptr()[])
            var rhs = fold(v.rhs.ptr()[])
            match lhs:
                case .int_literal(a):
                    match rhs:
                        case .int_literal(b):
                            var result = binary(v.op, a.value, b.value)
                            if result:
                                return CConstExpr.int_literal(IntLiteral(result.value().copy()))
                        case _:
                            pass
                case _:
                    pass
            return CConstExpr.c_binary_expr(
                CBinaryExpr(v.op.copy(), ArcPointer(lhs^), ArcPointer(rhs^))
            )
        case .c_cast_expr(v):
            return CConstExpr.c_cast_expr(
                CCastExpr(v.target.copy(), ArcPointer(fold(v.expr.ptr()[])))
            )
        case _:
            return expr.copy()


def combine(lhs: Optional[CType], rhs: Optional[CType]) -> Optional[CType]:
    if not lhs:
        return rhs.copy()
    if not rhs:
        return lhs.copy()
    match lhs.value():
        case .float_type(_):
            return lhs.copy()
        case .int_type(a):
            match rhs.value():
                case .float_type(_):
                    return rhs.copy()
                case .int_type(b):
                    if b.size_bytes > a.size_bytes or (
                        a.size_bytes == b.size_bytes
                        and not a.int_kind.value().startswith("U")
                        and b.int_kind.value().startswith("U")
                    ):
                        return rhs.copy()
                case _:
                    pass
        case _:
            pass
    return lhs.copy()


struct ConstExprParser(Copyable, Movable):
    var abi: TargetABI
    var literal_resolver: LiteralResolver
    var macro_values: Dict[String, ParsedConstExpr]
    var stream: List[String]
    var index: Int

    def __init__(out self, args: List[String]) raises:
        self.abi = probe_target_abi(args)
        self.literal_resolver = LiteralResolver(args)
        self.macro_values = Dict[String, ParsedConstExpr]()
        self.stream = List[String]()
        self.index = 0

    def peek(self) -> String:
        return self.stream[self.index].copy() if self.index < len(self.stream) else String()

    def pop(mut self) raises -> String:
        if self.index >= len(self.stream):
            raise Error("unexpected end of expression")
        var value = self.stream[self.index].copy()
        self.index += 1
        return value^

    def parse_tokens(mut self, input: List[String]) raises -> Optional[ParsedConstExpr]:
        if not len(input):
            return None
        var start = 0
        var end = len(input)
        while end - start >= 2 and input[start] == "(" and input[end - 1] == ")":
            var depth = 0
            var outer = True
            for i in range(start, end):
                if input[i] == "(":
                    depth += 1
                elif input[i] == ")":
                    depth -= 1
                if depth == 0 and i != end - 1:
                    outer = False
            if not outer:
                break
            start += 1
            end -= 1
        if (
            end - start == 5
            and input[start] == "("
            and input[start + 1] == "void"
            and input[start + 2] == "*"
            and input[start + 3] == ")"
            and (input[start + 4] == "0" or input[start + 4] == "NULL")
        ):
            return ParsedConstExpr(
                CConstExpr.c_null_ptr_literal(CNullPtrLiteral()), CType.void_type(VoidType())
            )
        self.stream = input.copy()
        self.index = 0
        try:
            var parsed = self.parse_expr(0)
            if self.index != len(self.stream):
                return None
            return parsed^
        except:
            return None

    def parse_expr(mut self, minimum: Int) raises -> ParsedConstExpr:
        var lhs = self.prefix()
        while self.peek():
            var op = self.peek()
            if op == "?" and minimum <= 0:
                _ = self.pop()
                var yes = self.parse_expr(0)
                if self.pop() != ":":
                    raise Error("expected colon")
                var no = self.parse_expr(0)
                var condition = fold(lhs.expr)
                match condition:
                    case .int_literal(v):
                        lhs = yes.copy() if v.value.digits != "0" else no.copy()
                    case _:
                        raise Error("nonconstant ternary condition")
                continue
            var prec = precedence(op)
            if prec < minimum:
                break
            _ = self.pop()
            var rhs = self.parse_expr(prec + 1)
            var kind = combine(lhs.primitive, rhs.primitive)
            lhs = ParsedConstExpr(
                CConstExpr.c_binary_expr(
                    CBinaryExpr(op^, ArcPointer(lhs.expr.copy()), ArcPointer(rhs.expr.copy()))
                ),
                kind^,
            )
        return lhs^

    def prefix(mut self) raises -> ParsedConstExpr:
        var token = self.pop()
        if token == "sizeof":
            if self.pop() != "(":
                raise Error("expected sizeof type")
            var name = String()
            var depth = 1
            while depth:
                var item = self.pop()
                if item == "(":
                    depth += 1
                elif item == ")":
                    depth -= 1
                if depth:
                    if name:
                        name += " "
                    name += item
            var kind = self.literal_resolver.for_spelling(name)
            if not kind:
                raise Error("unsupported sizeof type")
            var target = CType.int_type(kind.value().copy())
            return ParsedConstExpr(
                CConstExpr.c_size_of_expr(CSizeOfExpr(ArcPointer(target.copy()))), target^
            )
        if token == "(":
            var i = self.index
            if (
                i + 2 < len(self.stream)
                and identifier(self.stream[i])
                and self.stream[i + 1] == ")"
                and (
                    self.stream[i + 2] == "-"
                    or self.stream[i + 2] == "+"
                    or self.stream[i + 2] == "~"
                    or self.stream[i + 2] == "!"
                    or self.stream[i + 2] == "("
                )
            ):
                var kind = self.literal_resolver.for_spelling(self.stream[i])
                if kind:
                    self.index = i + 2
                    var operand = self.prefix()
                    var target = CType.int_type(kind.value().copy())
                    return ParsedConstExpr(
                        CConstExpr.c_cast_expr(
                            CCastExpr(ArcPointer(target.copy()), ArcPointer(operand.expr.copy()))
                        ),
                        target^,
                    )
            var inner = self.parse_expr(0)
            if self.pop() != ")":
                raise Error("expected closing parenthesis")
            return inner^
        if token == "+" or token == "-" or token == "~" or token == "!":
            var inner = self.prefix()
            return ParsedConstExpr(
                CConstExpr.c_unary_expr(CUnaryExpr(token^, ArcPointer(inner.expr.copy()))),
                inner.primitive.copy(),
            )
        return self.leaf(token)

    def leaf(mut self, token: String) raises -> ParsedConstExpr:
        var bytes = token.as_bytes()
        if token.startswith('"') and token.endswith('"'):
            var value = decode_escapes(String(token[byte = 1 : len(bytes) - 1]))
            while self.peek().startswith('"') and self.peek().endswith('"'):
                var next = self.pop()
                value += decode_escapes(String(next[byte = 1 : next.byte_length() - 1]))
            return ParsedConstExpr(
                CConstExpr.string_literal(StringLiteral(value^)),
                CType.int_type(IntType(IntKind.CHAR_S, 1, 1)),
            )
        if token.startswith("'") and token.endswith("'"):
            return ParsedConstExpr(
                CConstExpr.char_literal(
                    CharLiteral(decode_escapes(String(token[byte = 1 : len(bytes) - 1])))
                ),
                CType.int_type(IntType(IntKind.CHAR_S, 1, 1)),
            )
        if token == "NULL":
            return ParsedConstExpr(
                CConstExpr.c_null_ptr_literal(CNullPtrLiteral()), CType.void_type(VoidType())
            )
        var end = len(bytes)
        while end and (
            bytes[end - 1] == 85
            or bytes[end - 1] == 117
            or bytes[end - 1] == 76
            or bytes[end - 1] == 108
        ):
            end -= 1
        if end:
            var number = String(token[byte=0:end])
            var suffix = String(token[byte=end:])
            var base = 10
            if number.startswith("0x") or number.startswith("0X"):
                base = 16
                var sliced = String(number[byte=2:])
                number = sliced^
            elif number.byte_length() > 1 and number.startswith("0"):
                # Match Python int(text,0): nonzero legacy octal is rejected.
                for b in number.as_bytes():
                    if b != 48:
                        base = 0
            if base:
                try:
                    var value = BigInteger.parse(number, base).value()
                    var kind = self.literal_resolver.for_suffix(suffix)
                    return ParsedConstExpr(
                        CConstExpr.int_literal(IntLiteral(value^)), CType.int_type(kind^)
                    )
                except:
                    pass
        end = len(bytes)
        while end and (
            bytes[end - 1] == 70
            or bytes[end - 1] == 102
            or bytes[end - 1] == 76
            or bytes[end - 1] == 108
        ):
            end -= 1
        if end and ((bytes[0] >= 48 and bytes[0] <= 57) or bytes[0] == 46):
            var number = String(token[byte=0:end])
            var suffix = String(token[byte=end:]).lower()
            try:
                if number.startswith("0x") or number.startswith("0X"):
                    _ = parse_hex_float(number)
                else:
                    _ = parse_float(number)
                var kind = FloatKind.DOUBLE
                if "f" in suffix:
                    kind = FloatKind.FLOAT
                elif "l" in suffix:
                    kind = FloatKind.LONG_DOUBLE
                var size = 0
                var align: Optional[Int] = {}
                for item in self.abi.float_abi:
                    if item.kind == kind:
                        size = item.size_bytes
                        align = item.align_bytes
                return ParsedConstExpr(
                    CConstExpr.c_float_literal(CFloatLiteral(token.copy())),
                    CType.float_type(FloatType(kind, size, align)),
                )
            except:
                pass
        if identifier(token):
            if token in self.macro_values:
                return self.macro_values[token].copy()
            return ParsedConstExpr(
                CConstExpr.c_ref_expr(CRefExpr(token.copy())), CType.int_type(default_int())
            )
        raise Error("unsupported expression token")

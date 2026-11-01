from mojo_bindgen.parsing.lowering.macro_env import expand_object_like_macro_tokens
from mojo_bindgen.parsing.lowering.macro_fallback import ClangMacroFallback
from mojo_bindgen.parsing.lowering.const_expr import ConstExprParser, fold
from mojo_bindgen.parsing.lowering._integer import BigInteger, binary
from mojo_bindgen._numbers import IntegerValue
from std.testing import assert_equal, assert_true, TestSuite


def test_large_integer() raises:
    var a = BigInteger.parse("340282366920938463463374607431768211455").value()
    assert_equal(
        binary("+", a, IntegerValue(1)).value().digits, "340282366920938463463374607431768211456"
    )
    assert_equal(binary("%", IntegerValue(-7), IntegerValue(3)).value().digits, "2")
    assert_equal(binary(">>", IntegerValue(-7), IntegerValue(2)).value().digits, "-2")


def test_expression() raises:
    var parser = ConstExprParser([])
    var result = parser.parse_tokens(["1", "<<", "100"])
    assert_true(Bool(result))
    var value = fold(result.value().expr)
    match value:
        case .int_literal(v):
            assert_equal(v.value.digits, "1267650600228229401496703205376")
        case _:
            raise Error("expression did not fold")


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()


def test_macro_fallback_and_expansion() raises:
    var fallback = ClangMacroFallback([], ["-xc", "-DFOLDED=((int)(3))"])
    assert_equal(fallback.evaluate_integer("FOLDED").value().digits, "3")
    var env: Dict[String, List[String]] = {"A": ["B"], "B": ["A", "+", "1"]}
    var expanded = expand_object_like_macro_tokens(["A"], env)
    assert_equal(len(expanded), 3)
    assert_equal(expanded[0], "A")
    var limited = expand_object_like_macro_tokens(["A"], env, 1)
    assert_equal(len(limited), 1)
    assert_equal(limited[0], "B")

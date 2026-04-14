// Stress fixture for supported and unsupported macro forms.

#ifndef STRESS_MACROS_INPUT_H
#define STRESS_MACROS_INPUT_H

// Supported today: integer, float, string, char, null, reference, unary, and
// nested integer binary expressions.
// Tests integer literal macro,  preservation.
#define MACRO_INT 42u
// Tests decimal float literal, preservation.
#define MACRO_FLOAT 3.14159265
// Tests hexadecimal float literal, preservation.
#define MACRO_HEX_FLOAT 0x1.0p4
// Tests long-double suffix, preservation.
#define MACRO_LDOUBLE 1.0L
// Tests string literal macro, preservation.
#define MACRO_STRING "bindgen"
// Tests character literal macro, preservation.
#define MACRO_CHAR 'x'
// Tests null-pointer macro, preservation through nested parentheses.
#define MACRO_NULL ((void *)0)
// Tests macro reference to an earlier constant.
#define MACRO_REF MACRO_INT
// Tests forward macro reference to a later definition.
#define MACRO_FWD_REF MACRO_LATER
// Tests later target of a forward macro reference.
#define MACRO_LATER 17
// Tests predefined __LINE__ token, preservation as a predefined macro.
#define MACRO_LINE __LINE__
// Tests predefined __FILE__ token, preservation as a predefined macro.
#define MACRO_FILE __FILE__
// Tests predefined __DATE__ token, preservation as a predefined macro.
#define MACRO_DATE __DATE__
// Tests predefined __TIME__ token, preservation as a predefined macro.
#define MACRO_TIME __TIME__
// Tests predefined __COUNTER__ token, preservation as a predefined macro.
#define MACRO_COUNTER __COUNTER__
// Tests standard predefined __STDC__ token, preservation as a predefined macro.
#define MACRO_STDC __STDC__
// Tests standard predefined __STDC_VERSION__ token, preservation as a predefined macro.
#define MACRO_STDC_VERSION __STDC_VERSION__
// Tests standard predefined __STDC_HOSTED__ token, preservation as a predefined macro.
#define MACRO_STDC_HOSTED __STDC_HOSTED__
// Tests feature-test predefined __STDC_NO_ATOMICS__ token, preservation as a predefined macro.
#define MACRO_STDC_NO_ATOMICS __STDC_NO_ATOMICS__
// Tests IEC 60559 predefined macro family preservation.
#define MACRO_STDC_IEC_60559_BFP __STDC_IEC_60559_BFP__
// Tests header version predefined macro family preservation.
#define MACRO_STDC_VERSION_STDIO_H __STDC_VERSION_STDIO_H__
// Tests self-referential macro handling without recursive expansion.
#define MACRO_SELF MACRO_SELF
// Tests unary minus over an integer literal.
#define MACRO_NEG -7
// Tests bitwise-not unary integer expression.
#define MACRO_NOT (~0x3u)
// Tests simple binary OR expression.
#define MACRO_OR (0x1u | 0x2u)
// Tests shift expression preservation.
#define MACRO_SHIFT (1u << 3)
// Tests nested integer binary expressions with unary subexpression.
#define MACRO_COMPLEX_INT ((0x1u | 0x2u) & ~0x4u)
// Tests multi-operator integer expression preservation.
#define MACRO_ADD3 (1 + 2 + 3)

// Unsupported today: sizeof, casts, ternary, function-like, token pasting,
// stringification.
// Tests empty macro definition being preserved.
#define MACRO_EMPTY
// Tests macro body that expands to a type / keywords.
#define MACRO_TYPE unsigned int
// Tests sizeof-based macro expression, rejection.
#define MACRO_SIZEOF sizeof(int)
// Tests cast expression, rejection.
#define MACRO_CAST ((int)1)
// Tests ternary expression, rejection.
#define MACRO_TERNARY ((1) ? 2 : 3)
// Tests conditional expression with comparison, rejection.
#define MACRO_COND (1 > 0 ? 1 : 0)
// Tests compound-assignment expression, rejection.
#define MACRO_ASSIGN (x += 1)
// Tests comma-operator expression, rejection.
#define MACRO_COMMA (1, 2)
// Tests adjacent string-literal concatenation, rejection.
#define MACRO_CONCAT_STR "hello" " world"
// Tests attribute tokens in a macro body.
#define MACRO_ATTR __attribute__((aligned(16)))
// Tests __declspec tokens in a macro body.
#define MACRO_DECLSPEC __declspec(dllexport)
// Tests ordinary function-like macro, rejection.
#define MACRO_FUNC(x) ((x) + 1)
// Tests variadic function-like macro, rejection.
#define MACRO_VA(...) __VA_ARGS__
// Tests GNU variadic comma-elision macro, rejection.
#define MACRO_VA_GNU(fmt, ...) fmt, ##__VA_ARGS__
// Tests __VA_OPT__ macro, rejection.
#define MACRO_VA_OPT(x, ...) x __VA_OPT__(,) __VA_ARGS__
// Tests token-pasting macro, rejection.
#define MACRO_CAT(a, b) a##b
// Tests stringification macro, rejection.
#define MACRO_STR(x) #x
// Tests _Generic selection macro, rejection.
#define MACRO_GENERIC _Generic(0, int: 42, default: 0)

#endif

// Stress fixture for supported and unsupported macro forms.

#ifndef STRESS_MACROS_INPUT_H
#define STRESS_MACROS_INPUT_H

// Supported today: integer, float, string, char, null, reference, unary, and
// nested integer binary expressions.
#define MACRO_INT 42u
#define MACRO_FLOAT 3.14159265
#define MACRO_HEX_FLOAT 0x1.0p4
#define MACRO_LDOUBLE 1.0L
#define MACRO_STRING "bindgen"
#define MACRO_CHAR 'x'
#define MACRO_NULL ((void *)0)
#define MACRO_REF MACRO_INT
#define MACRO_FWD_REF MACRO_LATER
#define MACRO_LATER 17
#define MACRO_LINE __LINE__
#define MACRO_FILE __FILE__
#define MACRO_DATE __DATE__
#define MACRO_COUNTER __COUNTER__
#define MACRO_SELF MACRO_SELF
#define MACRO_NEG -7
#define MACRO_NOT (~0x3u)
#define MACRO_OR (0x1u | 0x2u)
#define MACRO_SHIFT (1u << 3)
#define MACRO_COMPLEX_INT ((0x1u | 0x2u) & ~0x4u)
#define MACRO_ADD3 (1 + 2 + 3)

// Unsupported today: sizeof, casts, ternary, function-like, token pasting,
// stringification.
#define MACRO_EMPTY
#define MACRO_TYPE unsigned int
#define MACRO_SIZEOF sizeof(int)
#define MACRO_CAST ((int)1)
#define MACRO_TERNARY ((1) ? 2 : 3)
#define MACRO_COND (1 > 0 ? 1 : 0)
#define MACRO_ASSIGN (x += 1)
#define MACRO_COMMA (1, 2)
#define MACRO_CONCAT_STR "hello" " world"
#define MACRO_ATTR __attribute__((aligned(16)))
#define MACRO_DECLSPEC __declspec(dllexport)
#define MACRO_FUNC(x) ((x) + 1)
#define MACRO_VA(...) __VA_ARGS__
#define MACRO_VA_GNU(fmt, ...) fmt, ##__VA_ARGS__
#define MACRO_VA_OPT(x, ...) x __VA_OPT__(,) __VA_ARGS__
#define MACRO_CAT(a, b) a##b
#define MACRO_STR(x) #x
#define MACRO_GENERIC _Generic(0, int: 42, default: 0)

#endif

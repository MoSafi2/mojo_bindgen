// Pathological macro stress fixture covering supported and unsupported forms.

#ifndef PATHOLOGICAL_MACROS_INPUT_H
#define PATHOLOGICAL_MACROS_INPUT_H

// Supported literal and expression forms.
#define PM_INT 42u
#define PM_FLOAT 3.14159265
#define PM_HEX_FLOAT 0x1.0p4
#define PM_LDOUBLE 1.0L
#define PM_STRING "bindgen"
#define PM_CHAR 'x'
#define PM_NULL ((void *)0)
#define PM_REF PM_INT
#define PM_FWD_REF PM_LATER
#define PM_LATER 17
#define PM_LINE __LINE__
#define PM_FILE __FILE__
#define PM_DATE __DATE__
#define PM_TIME __TIME__
#define PM_COUNTER __COUNTER__
#define PM_STDC __STDC__
#define PM_STDC_VERSION __STDC_VERSION__
#define PM_STDC_HOSTED __STDC_HOSTED__
#define PM_STDC_NO_ATOMICS __STDC_NO_ATOMICS__
#define PM_STDC_IEC_60559_BFP __STDC_IEC_60559_BFP__
#define PM_STDC_VERSION_STDIO_H __STDC_VERSION_STDIO_H__
#define PM_SELF PM_SELF
#define PM_NEG -7
#define PM_NOT (~0x3u)
#define PM_OR (0x1u | 0x2u)
#define PM_SHIFT (1u << 3)
#define PM_COMPLEX_INT ((0x1u | 0x2u) & ~0x4u)

// Unsupported but still preserved macro bodies.
#define PM_EMPTY
#define PM_TYPE unsigned int
#define PM_SIZEOF sizeof(int)
#define PM_CAST ((int)1)
#define PM_TERNARY ((1) ? 2 : 3)
#define PM_COND (1 > 0 ? 1 : 0)
#define PM_ASSIGN (x += 1)
#define PM_COMMA (1, 2)
#define PM_CONCAT_STR "hello" " world"
#define PM_ATTR __attribute__((aligned(16)))
#define PM_DECLSPEC __declspec(dllexport)
#define PM_FUNC(x) ((x) + 1)
#define PM_VA(...) __VA_ARGS__
#define PM_VA_GNU(fmt, ...) fmt, ##__VA_ARGS__
#define PM_VA_OPT(x, ...) x __VA_OPT__(,) __VA_ARGS__
#define PM_CAT(a, b) a##b
#define PM_STR(x) #x
#define PM_GENERIC _Generic(0, int: 42, default: 0)

#endif

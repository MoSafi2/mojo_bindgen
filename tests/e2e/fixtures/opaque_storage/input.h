#include <stddef.h>
#include <stdint.h>

typedef struct Extended { long double real; _Complex long double pair; } Extended;
typedef struct Guarded { uint64_t before; Extended values[2]; uint64_t after; } Guarded;
typedef long double (*extended_callback)(long double value);
extern long double extended_global;
long double unsupported_echo(long double value);
void unsupported_callback(extended_callback callback);
Extended *extended_fixture(void);
void extended_set(Extended *value);
int extended_check(Extended *value);
int extended_guard(void);
size_t extended_size(void);
size_t extended_align(void);
size_t extended_stride(void);
#define EXTENDED_LITERAL 1.0L

typedef union ExtendedUnion { long double value; int small; } ExtendedUnion;
size_t extended_union_size(void);
size_t extended_union_align(void);

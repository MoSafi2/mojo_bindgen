#ifndef FULL_SURFACE_RUNTIME_H
#define FULL_SURFACE_RUNTIME_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define SURF_MAGIC 17
#define SURF_FLAG_A 0x01u
#define SURF_FLAG_B 0x02u

typedef int32_t surf_i32;
typedef surf_i32 surf_alias_i32;

typedef enum surf_mode {
    SURF_ADD = 1,
    SURF_SUB = 2
} surf_mode;

struct surf_handle;

typedef struct surf_point {
    int32_t x;
    int32_t y;
} surf_point;

typedef struct surf_pair {
    surf_point lhs;
    surf_point rhs;
} surf_pair;

typedef union surf_num {
    int32_t as_i32;
    float as_f32;
} surf_num;

typedef struct surf_flags {
    unsigned int active : 1;
    unsigned int pending : 1;
    unsigned int priority : 4;
    unsigned int backend : 4;
    unsigned int : 22;
} surf_flags;

typedef struct surf_matrix {
    float transform[4][4];
} surf_matrix;

#pragma pack(push, 1)
typedef struct surf_packed_header {
    uint8_t flag;
    uint32_t length;
} surf_packed_header;
#pragma pack(pop)

typedef void (*surf_cb_t)(int32_t value, void *userdata);

extern const int32_t SURF_GLOBAL_CONST;

int32_t surf_add(surf_alias_i32 a, surf_alias_i32 b);
double surf_affine(double x, double scale, double bias);
int32_t surf_apply_mode(surf_mode mode, int32_t a, int32_t b);
bool surf_is_nonzero(int32_t value);
int32_t surf_union_from_int(int32_t value);
int32_t surf_flags_score(unsigned active, unsigned pending, unsigned priority, unsigned backend);
int32_t surf_packed_sum(uint8_t flag, uint32_t length);
int32_t surf_matrix_trace(float a00, float a11, float a22, float a33);
int32_t surf_global_plus(int32_t x);

void surf_fill_series(int32_t *out, int32_t n, int32_t start, int32_t step);
int32_t surf_sum_array(const int32_t *values, int32_t n);
int32_t surf_count_nonzero(volatile int32_t *values, int32_t n);
void surf_memory_copy(void *restrict dest, const void *restrict src, size_t n);
void surf_get_message(char **out_msg, int32_t *out_len);

struct surf_handle *surf_handle_new(int32_t seed);
int32_t surf_handle_get(const struct surf_handle *handle);
void surf_handle_free(struct surf_handle *handle);

void surf_install_callback(surf_cb_t cb, void *userdata);
int32_t surf_variadic_sum(int32_t count, ...);

static inline int32_t surf_inline_double(int32_t x) { return x * 2; }

#endif

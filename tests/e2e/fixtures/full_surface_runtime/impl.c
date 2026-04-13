#include "input.h"

#include <stdarg.h>
#include <stdlib.h>
#include <string.h>

const int32_t SURF_GLOBAL_CONST = 41;

struct surf_handle {
    int32_t value;
};

int32_t surf_add(surf_alias_i32 a, surf_alias_i32 b) { return a + b; }

double surf_affine(double x, double scale, double bias) { return (x * scale) + bias; }

int32_t surf_apply_mode(surf_mode mode, int32_t a, int32_t b) { return mode == SURF_SUB ? (a - b) : (a + b); }

bool surf_is_nonzero(int32_t value) { return value != 0; }

int32_t surf_union_from_int(int32_t value) {
    surf_num n = {.as_i32 = value};
    return n.as_i32;
}

int32_t surf_flags_score(unsigned active, unsigned pending, unsigned priority, unsigned backend) {
    surf_flags f = {0};
    f.active = active;
    f.pending = pending;
    f.priority = priority;
    f.backend = backend;
    return (int32_t)(f.active + (f.pending * 2) + (f.priority * 3) + (f.backend * 5));
}

int32_t surf_packed_sum(uint8_t flag, uint32_t length) {
    surf_packed_header h = {flag, length};
    return (int32_t)h.flag + (int32_t)h.length;
}

int32_t surf_matrix_trace(float a00, float a11, float a22, float a33) {
    surf_matrix m = {0};
    m.transform[0][0] = a00;
    m.transform[1][1] = a11;
    m.transform[2][2] = a22;
    m.transform[3][3] = a33;
    return (int32_t)(m.transform[0][0] + m.transform[1][1] + m.transform[2][2] + m.transform[3][3]);
}

int32_t surf_global_plus(int32_t x) { return SURF_GLOBAL_CONST + x; }

void surf_fill_series(int32_t *out, int32_t n, int32_t start, int32_t step) {
    for (int32_t i = 0; i < n; ++i) {
        out[i] = start + (i * step);
    }
}

int32_t surf_sum_array(const int32_t *values, int32_t n) {
    int32_t sum = 0;
    for (int32_t i = 0; i < n; ++i) {
        sum += values[i];
    }
    return sum;
}

int32_t surf_count_nonzero(volatile int32_t *values, int32_t n) {
    int32_t count = 0;
    for (int32_t i = 0; i < n; ++i) {
        if (values[i] != 0) {
            ++count;
        }
    }
    return count;
}

void surf_memory_copy(void *restrict dest, const void *restrict src, size_t n) { memcpy(dest, src, n); }

void surf_get_message(char **out_msg, int32_t *out_len) {
    static char kMessage[] = "bindgen-surface";
    *out_msg = kMessage;
    *out_len = (int32_t)(sizeof(kMessage) - 1);
}

struct surf_handle *surf_handle_new(int32_t seed) {
    struct surf_handle *h = (struct surf_handle *)malloc(sizeof(struct surf_handle));
    if (h == NULL) {
        return NULL;
    }
    h->value = seed * 10;
    return h;
}

int32_t surf_handle_get(const struct surf_handle *handle) {
    if (handle == NULL) {
        return -1;
    }
    return handle->value;
}

void surf_handle_free(struct surf_handle *handle) { free(handle); }

void surf_install_callback(surf_cb_t cb, void *userdata) {
    if (cb != NULL) {
        cb(7, userdata);
    }
}

int32_t surf_variadic_sum(int32_t count, ...) {
    va_list args;
    va_start(args, count);
    int32_t sum = 0;
    for (int32_t i = 0; i < count; ++i) {
        sum += va_arg(args, int32_t);
    }
    va_end(args);
    return sum;
}

// Broad supported stress fixture for parser + emitter regression coverage.
// Intentionally includes many C type forms, qualifiers, storage-class-ish
// declarations, anonymous/nested records, bit-fields, atomics, vectors,
// flexible arrays, zero-length arrays, function pointers, old-style arrays,
// packed/aligned records, complex numbers, and guarded compiler extensions.

#ifndef STRESS_NORMAL_INPUT_H
#define STRESS_NORMAL_INPUT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdalign.h>
#include <stdatomic.h>
#include <complex.h>
#include <wchar.h>
#include <uchar.h>
#include <stdnoreturn.h>

#define EV_VERSION_MAJOR 4
#define EV_VERSION_MINOR 33
#define EV_MAXPRI 9
#define EV_FLAG_AUTO 0x00000001u
#define EV_FLAG_DYNAMIC 0x00000002u
#define EV_FLAG_MASK 0x0000FFFFu

#define EV_STRINGIFY_(x) #x
#define EV_STRINGIFY(x) EV_STRINGIFY_(x)
#define EV_JOIN_(a, b) a##b
#define EV_JOIN(a, b) EV_JOIN_(a, b)

#define EV_TYPE int
#define EV_ARRAY_LEN 16
#define EV_NAME_LITERAL "stress-normal-input"

_Static_assert(sizeof(uint8_t) == 1, "uint8_t must be 1 byte");
_Static_assert(_Alignof(max_align_t) >= _Alignof(void *), "unexpected alignment");

struct ev_loop;
struct ev_watcher;

typedef enum ev_backend {
    EVBACKEND_SELECT = 0x00000001,
    EVBACKEND_POLL = 0x00000002,
    EVBACKEND_EPOLL = 0x00000004,
    EVBACKEND_MASK = 0x0000FFFF
} ev_backend;

enum ev_run_flags {
    EVRUN_NOWAIT = 1,
    EVRUN_ONCE = 2
};

enum {
    EV_UNDEF = -1,
    EV_NONE = 0x00,
    EV_READ = 0x01,
    EV_WRITE = 0x02
};

typedef struct ev_tstamp_pair {
    double at;
    double repeat;
} ev_tstamp_pair;

typedef struct ev_io {
    int active;
    int pending;
    void *data;
    int fd;
    int events;
} ev_io;

typedef struct ev_stat {
    ev_tstamp_pair prev;
    ev_tstamp_pair curr;
    const char *path;
    uint32_t interval;
} ev_stat;

typedef union ev_any_watcher {
    ev_io io;
    ev_stat stat;
} ev_any_watcher;

typedef struct ev_prepare_batch {
    void *watchers[16];
    int count;
    uint8_t id[4];
} ev_prepare_batch;

typedef struct ev_watcher_list {
    struct ev_watcher *next;
    void (*cb)(struct ev_loop *);
    void *data;
} ev_watcher_list;

typedef double ev_tstamp;
typedef ev_tstamp ev_time_t;
typedef uint32_t ev_eventmask;
typedef struct ev_loop *ev_loop_ptr;
typedef void (*ev_cb_t)(struct ev_loop *, void *, int);

uint32_t ev_version_major(void);
struct ev_loop *ev_loop_new(unsigned int flags);
void ev_io_init(ev_io *w, ev_cb_t cb, int fd, int events);
int ev_stat_path_watch(const ev_stat *w, const char *path);
ev_tstamp_pair ev_now_pair(struct ev_loop *loop);
void ev_set_userdata(struct ev_loop *loop, void *data, ...);
void ev_feed_event_batch(struct ev_loop *loop, int *events, int count);
void ev_get_version_string(char **out_version);
int ev_process_argv(int argc, char ***argv);

extern int ev_global_error_code;
extern const char *ev_backend_name;

typedef struct ev_packet {
    int length;
    int type;
    uint8_t payload[];
} ev_packet;

#pragma pack(push, 1)
typedef struct ev_packed_header {
    uint8_t flag;
    uint32_t length;
} ev_packed_header;
#pragma pack(pop)

struct ev_aligned_data {
    char a;
    int b __attribute__((aligned(16)));
};

bool ev_is_active(struct ev_loop *loop);

typedef struct ev_matrix {
    float transform[4][4];
} ev_matrix;

void ev_atomic_add(volatile int *counter, int amount);
void ev_memory_copy(void *restrict dest, const void *restrict src, size_t n);

struct ev_node {
    struct ev_node *next;
    struct ev_node *prev;
};

typedef struct ev_a ev_a;
struct ev_a {
    ev_a *next;
};

typedef EV_TYPE ev_dynamic_t;

static int ev_internal_state;
extern const struct ev_loop *ev_default_loop;

struct ev_pad {
    char a;
    int b;
    char c;
};

/* ------------------------------------------------------------------------- */
/* Primitive aliases and qualifier-heavy typedefs                            */
/* ------------------------------------------------------------------------- */

typedef signed char ev_i8;
typedef unsigned char ev_u8;
typedef short ev_i16;
typedef unsigned short ev_u16;
typedef int ev_i32;
typedef unsigned int ev_u32;
typedef long ev_long_t;
typedef unsigned long ev_ulong_t;
typedef long long ev_i64;
typedef unsigned long long ev_u64;

typedef float ev_f32;
typedef double ev_f64;
typedef long double ev_f128ish;

typedef char ev_char_t;
typedef signed char ev_schar_t;
typedef unsigned char ev_uchar_t;

typedef wchar_t ev_wchar_t;
typedef char16_t ev_char16_t;
typedef char32_t ev_char32_t;

typedef intptr_t ev_intptr_t;
typedef uintptr_t ev_uintptr_t;
typedef ptrdiff_t ev_ptrdiff_t;
typedef size_t ev_size_t;
typedef max_align_t ev_max_align_t;

typedef const int ev_const_int_t;
typedef volatile int ev_volatile_int_t;
typedef const volatile int ev_cv_int_t;

typedef int *ev_int_ptr;
typedef const int *ev_const_int_ptr;
typedef int *const ev_const_ptr_to_int;
typedef const int *const ev_const_ptr_to_const_int;
typedef volatile int *ev_volatile_int_ptr;
typedef const volatile int *ev_cv_int_ptr;

/* ------------------------------------------------------------------------- */
/* _Bool / enum / typedef layering                                           */
/* ------------------------------------------------------------------------- */

typedef _Bool ev_bool_alias;

typedef enum ev_small_enum {
    EV_SMALL_ZERO = 0,
    EV_SMALL_ONE = 1
} ev_small_enum;

typedef enum ev_backend ev_backend_alias;
typedef enum ev_run_flags ev_run_flags_alias;

/* ------------------------------------------------------------------------- */
/* Arrays and nested arrays                                                  */
/* ------------------------------------------------------------------------- */

typedef int ev_int_array_4[4];
typedef int ev_int_matrix_3x5[3][5];
typedef const char *ev_string_table_2x3[2][3];

typedef struct ev_array_holder {
    int fixed[8];
    int matrix[2][3];
    const char *names[4];
    unsigned char bytes[EV_ARRAY_LEN];
} ev_array_holder;

/* ------------------------------------------------------------------------- */
/* Function pointer types                                                    */
/* ------------------------------------------------------------------------- */

typedef void (*ev_void_fn_t)(void);
typedef int (*ev_unary_int_fn_t)(int);
typedef int (*ev_binary_int_fn_t)(int, int);
typedef void (*ev_variadic_cb_t)(const char *fmt, ...);
typedef int *(*ev_ret_int_ptr_fn_t)(int *);
typedef void (*ev_array_param_fn_t)(int arr[static 4]);
typedef int (*ev_vla_param_fn_t)(size_t n, int arr[n]);
typedef int (*ev_loop_transform_cb_t)(struct ev_loop *, void *, int);

typedef struct ev_callbacks {
    ev_void_fn_t on_start;
    ev_unary_int_fn_t transform;
    ev_variadic_cb_t vlog;
    ev_cb_t watcher_cb;
    int (*cmp)(const void *, const void *);
} ev_callbacks;

/* ------------------------------------------------------------------------- */
/* Records with anonymous / nested / self-referential structure              */
/* ------------------------------------------------------------------------- */

typedef struct ev_nested_anon {
    int tag;
    struct {
        int x;
        int y;
    };
    union {
        uint32_t u32;
        float f32;
        struct {
            uint16_t lo;
            uint16_t hi;
        };
    };
} ev_nested_anon;

struct ev_deep_node {
    struct ev_deep_node *next;
    union {
        int as_int;
        struct {
            short left;
            short right;
        } pair;
    } payload;
};

typedef struct ev_recursive_tree {
    struct ev_recursive_tree *left;
    struct ev_recursive_tree *right;
    union {
        int i;
        double d;
        void *p;
    } value;
} ev_recursive_tree;

/* ------------------------------------------------------------------------- */
/* Bit-fields                                                                */
/* ------------------------------------------------------------------------- */

typedef struct ev_bits {
    unsigned ready : 1;
    unsigned error : 1;
    unsigned state : 3;
    unsigned code : 11;
    unsigned : 0; /* force alignment to next storage unit */
    signed delta : 7;
    _Bool enabled : 1;
} ev_bits;

typedef union ev_bits_overlay {
    ev_bits bits;
    uint32_t raw;
} ev_bits_overlay;

/* ------------------------------------------------------------------------- */
/* Flexible array / zero-length / packet-like records                        */
/* ------------------------------------------------------------------------- */

typedef struct ev_blob {
    size_t size;
    unsigned char data[];
} ev_blob;

#if defined(__GNUC__) || defined(__clang__)
typedef struct ev_blob0 {
    size_t size;
    unsigned char data[0];
} ev_blob0;
#endif

/* ------------------------------------------------------------------------- */
/* Qualified pointers, restrict, volatile, atomic                            */
/* ------------------------------------------------------------------------- */

typedef _Atomic int ev_atomic_int_t;
typedef _Atomic unsigned int ev_atomic_uint_t;
typedef _Atomic(void *) ev_atomic_void_ptr_t;

typedef struct ev_atomic_holder {
    _Atomic int counter;
    _Atomic uint32_t flags;
    _Atomic(void *) user;
} ev_atomic_holder;

extern _Atomic int ev_global_atomic_counter;
extern volatile uint32_t ev_mmio_status_reg;
extern const volatile uint32_t *ev_mmio_base;

/* ------------------------------------------------------------------------- */
/* Complex numbers                                                           */
/* ------------------------------------------------------------------------- */

typedef float _Complex ev_cfloat;
typedef double _Complex ev_cdouble;
typedef long double _Complex ev_cldouble;

typedef struct ev_complex_pair {
    double _Complex z0;
    float _Complex z1;
} ev_complex_pair;

/* ------------------------------------------------------------------------- */
/* Alignment, packing, attribute-heavy declarations                          */
/* ------------------------------------------------------------------------- */

typedef struct ev_alignas_block {
    alignas(32) unsigned char storage[32];
    alignas(16) int lanes[4];
} ev_alignas_block;

#if defined(__GNUC__) || defined(__clang__)
typedef struct __attribute__((packed)) ev_gnu_packed_bits {
    uint8_t a;
    uint16_t b;
    uint32_t c;
} ev_gnu_packed_bits;

typedef struct __attribute__((aligned(64))) ev_cacheline_block {
    unsigned char payload[64];
} ev_cacheline_block;
#endif

/* ------------------------------------------------------------------------- */
/* Typedefs to arrays / pointers / function pointers                         */
/* ------------------------------------------------------------------------- */

typedef int ev_row4_t[4];
typedef ev_row4_t ev_matrix2x4_t[2];
typedef int (*ev_row_ptr_t)[4];
typedef void (*ev_signal_table_t[3])(int);

/* ------------------------------------------------------------------------- */
/* Unions with punning-like layouts                                          */
/* ------------------------------------------------------------------------- */

typedef union ev_number {
    int i;
    unsigned u;
    long l;
    float f;
    double d;
    void *p;
} ev_number;

typedef union ev_ptr_cast {
    void *vp;
    const void *cvp;
    uintptr_t addr;
    char *cp;
    int *ip;
} ev_ptr_cast;

/* ------------------------------------------------------------------------- */
/* Opaque / incomplete / forward-declared tags                               */
/* ------------------------------------------------------------------------- */

struct ev_incomplete_only;
union ev_incomplete_union;
enum ev_incomplete_enum;

typedef struct ev_incomplete_only ev_incomplete_only_t;
typedef union ev_incomplete_union ev_incomplete_union_t;

/* ------------------------------------------------------------------------- */
/* Typedef-name reuse and tag/typedef interactions                           */
/* ------------------------------------------------------------------------- */

typedef struct ev_typedef_struct {
    int value;
} ev_typedef_struct;

typedef union ev_typedef_union {
    int i;
    float f;
} ev_typedef_union;

typedef enum ev_typedef_enum {
    EV_TENUM_A = 1,
    EV_TENUM_B = 2
} ev_typedef_enum;

/* ------------------------------------------------------------------------- */
/* const/volatile on arrays and pointees                                     */
/* ------------------------------------------------------------------------- */

typedef const int ev_const_arr_4[4];
typedef volatile int ev_volatile_arr_4[4];
typedef const volatile int ev_cv_arr_4[4];

typedef struct ev_cv_payload {
    const int *a;
    volatile int *b;
    const volatile int *c;
    int *const pinned;
} ev_cv_payload;

/* ------------------------------------------------------------------------- */
/* Compiler extension types                                                  */
/* ------------------------------------------------------------------------- */

#if defined(__SIZEOF_INT128__)
typedef __int128 ev_i128;
typedef unsigned __int128 ev_u128;

typedef struct ev_i128_box {
    __int128 lohi;
    unsigned __int128 ulohi;
} ev_i128_box;
#endif

#if defined(__GNUC__) || defined(__clang__)
typedef int ev_v4si __attribute__((vector_size(16)));
typedef float ev_v4sf __attribute__((vector_size(16)));

typedef union ev_vector_union {
    ev_v4si vi;
    ev_v4sf vf;
    int scalars[4];
    float lanes[4];
} ev_vector_union;
#endif

/* ------------------------------------------------------------------------- */
/* Parameter edge cases                                                       */
/* ------------------------------------------------------------------------- */

void ev_take_const_ptr(const int *p);
void ev_take_const_ptr_const(const int *const p);
void ev_take_cv_ptr(const volatile int *p);
void ev_take_restrict_buffers(void *restrict dst, const void *restrict src, size_t n);

int ev_sum_fixed4(const int a[4]);
int ev_sum_static4(const int a[static 4]);
int ev_sum_vla(size_t n, const int a[n]);
void ev_fill_vla(size_t n, int a[n], int value);

int (*ev_choose_binary_op(int which))(int, int);
int (*ev_get_signal_table(void))[3];

int ev_accept_fn(int (*fn)(int));
int ev_accept_variadic(void (*fn)(const char *, ...));

/* ------------------------------------------------------------------------- */
/* Return type edge cases                                                    */
/* ------------------------------------------------------------------------- */

const char *ev_get_name(void);
void *ev_get_context(struct ev_loop *loop);
const struct ev_loop *ev_get_const_loop(void);
int *ev_get_counter_ptr(void);
int (*ev_get_transformer(void))(int);
ev_tstamp_pair ev_make_pair(double at, double repeat);

/* ------------------------------------------------------------------------- */
/* Inline / noreturn / storage flavor                                        */
/* ------------------------------------------------------------------------- */

static inline int ev_inline_add(int a, int b) {
    return a + b;
}

noreturn void ev_fatal(const char *message);

/* ------------------------------------------------------------------------- */
/* Old-school declarator stress                                              */
/* ------------------------------------------------------------------------- */

extern int *ev_ptr_array[3];
extern int (*ev_array_of_fn_ptrs[2])(int);
extern int (*(*ev_fn_returning_array_ptr(void))[4]);

/* ------------------------------------------------------------------------- */
/* Designated-init friendly records                                          */
/* ------------------------------------------------------------------------- */

typedef struct ev_designated {
    int id;
    const char *name;
    struct {
        int major;
        int minor;
    } version;
    union {
        int i;
        double d;
    } data;
} ev_designated;

/* ------------------------------------------------------------------------- */
/* More weird-but-valid record layouts                                       */
/* ------------------------------------------------------------------------- */

typedef struct ev_mixed_layout {
    char c0;
    double d0;
    short s0;
    void *p0;
    char c1;
} ev_mixed_layout;

typedef union ev_nested_union {
    struct {
        uint8_t tag;
        uint8_t payload[7];
    } bytes;
    uint64_t raw64;
    double as_double;
} ev_nested_union;

typedef struct ev_embedded_fnptrs {
    void (*start)(void);
    void (*stop)(void *);
    int (*poll)(struct ev_loop *, int timeout_ms);
} ev_embedded_fnptrs;

/* ------------------------------------------------------------------------- */
/* Tagged protocol-ish example                                               */
/* ------------------------------------------------------------------------- */

enum ev_payload_kind {
    EV_PAYLOAD_INT = 1,
    EV_PAYLOAD_FLOAT = 2,
    EV_PAYLOAD_PTR = 3
};

typedef struct ev_tagged_payload {
    enum ev_payload_kind kind;
    union {
        int i;
        float f;
        void *p;
    } as;
} ev_tagged_payload;

/* ------------------------------------------------------------------------- */
/* String-ish and character-ish types                                        */
/* ------------------------------------------------------------------------- */

typedef struct ev_text {
    char ascii[32];
    wchar_t wide[16];
    char16_t utf16[16];
    char32_t utf32[16];
} ev_text;

/* ------------------------------------------------------------------------- */
/* Globals                                                                   */
/* ------------------------------------------------------------------------- */

extern int ev_global_counter;
extern const int ev_global_limit;
extern char *ev_global_buffer;
extern const char ev_build_id[];
extern struct ev_node ev_global_list_head;
extern union ev_number ev_global_number;
extern ev_callbacks ev_global_callbacks;

#if defined(__GNUC__) || defined(__clang__)
extern __thread int ev_tls_errno_like;
#endif

/* ------------------------------------------------------------------------- */
/* API surface covering many forms                                           */
/* ------------------------------------------------------------------------- */

bool ev_is_active(struct ev_loop *loop);
void ev_atomic_add(volatile int *counter, int amount);
void ev_memory_copy(void *restrict dest, const void *restrict src, size_t n);

void ev_store_atomic(_Atomic int *dst, int value);
int ev_load_atomic(const _Atomic int *src);
void ev_swap_numbers(ev_number *a, ev_number *b);
size_t ev_blob_total_size(const ev_blob *blob);
int ev_call_loop_cb(ev_cb_t cb, struct ev_loop *loop, void *arg, int revents);
double _Complex ev_complex_mul(double _Complex a, double _Complex b);

#if defined(__GNUC__) || defined(__clang__)
ev_v4si ev_vector_add_i32(ev_v4si a, ev_v4si b);
#endif

#endif
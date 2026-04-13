// tests/fixtures/everything.h
//
// Exercises every C construct mojo-bindgen must handle.
// Compiled with: clang -x c -std=c11

#ifndef EVERYTHING_H
#define EVERYTHING_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

// ── 1. INTEGER MACROS ────────────────────────────────────────────────────────
// Simple literals → IRConst.  Expressions and strings are skipped.

#define EV_VERSION_MAJOR  4
#define EV_VERSION_MINOR  33
#define EV_MAXPRI         9
#define EV_FLAG_AUTO      0x00000001u
#define EV_FLAG_DYNAMIC   0x00000002u
#define EV_FLAG_MASK      0x0000FFFFu

// These must be skipped (non-integer or multi-token expression):
#define EV_PI             3.14159265      // float literal — skip
#define EV_LABEL          "libev"         // string — skip
#define EV_COMBINED       (EV_FLAG_AUTO | EV_FLAG_DYNAMIC)  // expression — skip

// ── 2. OPAQUE HANDLES ────────────────────────────────────────────────────────
// Forward-declared structs with no body → IROpaque in any pointer field.

struct ev_loop;          // no body: opaque handle
struct ev_watcher;       // no body: opaque handle

// ── 3. ENUMS ─────────────────────────────────────────────────────────────────
// Named enum → IREnum.  Anonymous enum → enumerants only, no type alias.

typedef enum ev_backend {
    EVBACKEND_SELECT  = 0x00000001,
    EVBACKEND_POLL    = 0x00000002,
    EVBACKEND_EPOLL   = 0x00000004,
    EVBACKEND_KQUEUE  = 0x00000008,
    EVBACKEND_DEVPOLL = 0x00000010,
    EVBACKEND_PORT    = 0x00000020,
    EVBACKEND_MASK    = 0x0000FFFF,
    EVBACKEND_COUNT   = 6
} ev_backend;

// Enum without typedef — still captured
enum ev_run_flags {
    EVRUN_NOWAIT = 1,
    EVRUN_ONCE   = 2
};

// Anonymous enum — values become top-level IRConst nodes, no IREnum
enum {
    EV_UNDEF  = -1,
    EV_NONE   = 0x00,
    EV_READ   = 0x01,
    EV_WRITE  = 0x02,
    EV_TIMER  = 0x00000100
};

// ── 4. PLAIN STRUCT ──────────────────────────────────────────────────────────

typedef struct ev_tstamp_pair {
    double at;       // IRPrimitive  float64  offset=0
    double repeat;   // IRPrimitive  float64  offset=8
} ev_tstamp_pair;

// ── 5. STRUCT WITH POINTER FIELDS ────────────────────────────────────────────

typedef struct ev_io {
    int      active;          // IRPrimitive  int32   offset=0
    int      pending;         // IRPrimitive  int32   offset=4
    void    *data;            // IRPointer(None)  →  OpaquePointer  offset=8
    int      fd;              // IRPrimitive  int32   offset=16
    int      events;          // IRPrimitive  int32   offset=20
} ev_io;

// ── 6. NESTED STRUCT (by value) ───────────────────────────────────────────────
// Field type resolves to IRStruct (already declared above).

typedef struct ev_stat {
    ev_tstamp_pair  prev;     // IRStruct  offset=0   size=16
    ev_tstamp_pair  curr;     // IRStruct  offset=16  size=16
    const char     *path;     // IRPointer(IRPrimitive "char", is_const=True)  offset=32
    uint32_t        interval; // IRPrimitive  uint32  offset=40
} ev_stat;

// ── 7. UNION ─────────────────────────────────────────────────────────────────
// is_union=True.  All fields share byte_offset=0.  size = largest member.

typedef union ev_any_watcher {
    ev_io    io;      // IRStruct  size=24
    ev_stat  stat;    // IRStruct  size=48  ← determines union size
} ev_any_watcher;

// ── 8. BITFIELD STRUCT ───────────────────────────────────────────────────────
// IRField.type = IRBitfield for each packed member.

typedef struct ev_flags {
    unsigned int active   : 1;   // IRBitfield  backing=uint32  offset=0  width=1
    unsigned int pending  : 1;   // IRBitfield  backing=uint32  offset=1  width=1
    unsigned int priority : 4;   // IRBitfield  backing=uint32  offset=2  width=4
    unsigned int backend  : 4;   // IRBitfield  backing=uint32  offset=6  width=4
    unsigned int          : 22;  // anonymous padding — emit as padding comment
} ev_flags;

// ── 9. FIXED-SIZE ARRAY FIELD ────────────────────────────────────────────────

typedef struct ev_prepare_batch {
    void    *watchers[16];   // IRArray(IRPointer(None), size=16)  →  InlineArray[OpaquePointer, 16]
    int      count;          // IRPrimitive  int32
    uint8_t  id[4];          // IRArray(IRPrimitive uint8, size=4)  →  InlineArray[UInt8, 4]
} ev_prepare_batch;

// ── 10. FUNCTION POINTER FIELDS ──────────────────────────────────────────────
// Each field type = IRFunctionPtr.  Emitted as OpaquePointer + comment.

typedef struct ev_watcher_list {
    struct ev_watcher  *next;                    // IRPointer → IROpaque("ev_watcher")
    void              (*cb)(struct ev_loop *);   // IRFunctionPtr  ret=void  params=[IRPointer(IROpaque)]
    void              *data;
} ev_watcher_list;

// ── 11. TYPEDEF CHAINS ───────────────────────────────────────────────────────
// TypeResolver must unroll these to the base IRPrimitive.

typedef double       ev_tstamp;          // → IRPrimitive float64
typedef ev_tstamp    ev_time_t;          // → IRPrimitive float64  (chain depth 2)
typedef uint32_t     ev_eventmask;       // → IRPrimitive uint32

// Typedef to a pointer
typedef struct ev_loop *ev_loop_ptr;     // → IRPointer(IROpaque("ev_loop"))

// Typedef to a function pointer
typedef void (*ev_cb_t)(struct ev_loop *, void *, int);
//  → IRFunctionPtr  ret=void  params=[ptr(opaque), ptr(void), int32]

// ── 12. FUNCTIONS ────────────────────────────────────────────────────────────

// Returns primitive
uint32_t ev_version_major(void);   // ret=IRPrimitive(uint32)  params=[]

// Takes opaque pointer (loop handle)
struct ev_loop *ev_loop_new(unsigned int flags);
// ret=IRPointer(IROpaque("ev_loop"))  params=[IRPrimitive(uint32)]

// Multiple pointer params
void ev_io_init(ev_io *w, ev_cb_t cb, int fd, int events);
// ret=void  params=[ptr(IRStruct ev_io), IRFunctionPtr(→OpaquePointer), int32, int32]

// Const pointer param (read-only input)
int ev_stat_path_watch(const ev_stat *w, const char *path);
// params=[IRPointer(IRStruct, is_const=True), IRPointer(IRPrimitive char, is_const=True)]

// Returns struct by value — rare in C APIs but legal
ev_tstamp_pair ev_now_pair(struct ev_loop *loop);

// Variadic — must be skipped, comment emitted
void ev_set_userdata(struct ev_loop *loop, void *data, ...);

// Function taking fixed array param (decays to pointer in C ABI)
void ev_feed_event_batch(struct ev_loop *loop, int *events, int count);
// int* — the array decays; emit as UnsafePointer[Int32]

// ── 13. DOUBLE POINTERS ────────────────────────────────────────────────────────
// Out-parameters or argv-style APIs: unroll ** → UnsafePointer[UnsafePointer[...]].

void ev_get_version_string(char **out_version);
int ev_process_argv(int argc, char ***argv); // Pointer to array of strings

// ── 14. GLOBAL VARIABLES ────────────────────────────────────────────────────
// Emit as exported symbols or skip; bindgen policy.
// Not Handled Today
extern int ev_global_error_code;
extern const char *ev_backend_name;

// ── 15. FLEXIBLE ARRAY MEMBERS (C99) ─────────────────────────────────────────
// Struct size excludes FAM; layout tests offset/size vs. Clang.

typedef struct ev_packet {
    int length;
    int type;
    uint8_t payload[]; // C99 FAM — size=8, offset=8 (padding handled)
} ev_packet;

// ── 16. PACKED STRUCTS & ALIGNMENT ────────────────────────────────────────────
// Offsets must match compiler layout (#pragma pack, __attribute__((aligned))).

#pragma pack(push, 1)
typedef struct ev_packed_header {
    uint8_t  flag;     // offset=0
    uint32_t length;   // offset=1 (not 4!)
} ev_packed_header;
#pragma pack(pop)

struct ev_aligned_data {
    char a;
    int b __attribute__((aligned(16))); // offset=16
};

// ── 17. BOOLEANS (<stdbool.h>) ────────────────────────────────────────────────
// _Bool/bool → native boolean in target, not raw Int8/Int32.

bool ev_is_active(struct ev_loop *loop);

// ── 18. MULTI-DIMENSIONAL ARRAYS ───────────────────────────────────────────────
// Naive recursive parsers often mishandle [N][M] fields.

typedef struct ev_matrix {
    float transform[4][4]; // → InlineArray[InlineArray[Float32, 4], 4]
} ev_matrix;

// ── 19. INLINE FUNCTIONS ──────────────────────────────────────────────────────
// No exported symbol in the DSO unless emitted separately; bindgen may skip.
// TODO FIX: Currently handled  as a function with linkname 
static inline int ev_fast_check(int x) {
    return x > 0 ? 1 : 0;
}

// ── 20. VOLATILE AND RESTRICT QUALIFIERS ───────────────────────────────────────
// Strip or preserve qualifiers without breaking type parsing.

void ev_atomic_add(volatile int *counter, int amount);
void ev_memory_copy(void *restrict dest, const void *restrict src, size_t n);

// ── 21. INCOMPLETE TYPE RESOLUTION EDGE CASES ────────────────────────────────
// Stress fixpoint type resolution with self-reference and typedef recursion.

struct ev_node {
    struct ev_node *next;
    struct ev_node *prev;
};

typedef struct ev_a ev_a;
struct ev_a {
    ev_a *next;
};

// ── 22. ENUM EDGE CASES ───────────────────────────────────────────────────────

// Large enum value crossing signed int boundary.
enum ev_big {
    EV_BIG = 0x7FFFFFFFFFFFFFFFLL
};


// ── 23. BITFIELD EDGE CASES ───────────────────────────────────────────────────
// Mix backing types, packing boundaries, and zero-width alignment reset.

struct ev_bf {
    unsigned char a : 3;
    signed int b : 5;
    _Bool c : 1;
};

struct ev_bf2 {
    unsigned int a : 20;
    unsigned int b : 20;
};

struct ev_bf3 {
    unsigned int a : 1;
    unsigned int : 0; // forces alignment reset
    unsigned int b : 1;
};

// ── 24. POINTER-TO-ARRAY VS ARRAY-OF-POINTERS ────────────────────────────────

int (*ev_ptr_to_array)[10];  // pointer to array[10] of int
int *ev_array_of_ptrs[10];   // array[10] of pointer to int

// ── 25. K&R / OLD-STYLE FUNCTION DECLARATION ─────────────────────────────────
// Legacy syntax still seen in older system headers.

int ev_legacy(a, b)
int a;
double b;
{
    (void)b;
    return a;
}

// ── 26. INLINE + EXTERN INLINE DECLARATIONS ──────────────────────────────────
// Important for symbol/linkage behavior differences vs static inline.

inline int ev_inline(int x);
extern inline int ev_extern_inline(int x);

// ── 27. MACRO-EXPANDED TYPE IN TYPEDEF ───────────────────────────────────────
// Validates macro expansion before typedef type resolution.

#define EV_TYPE int
typedef EV_TYPE ev_dynamic_t;

// ── 28. STATIC + EXTERN GLOBAL LINKAGE CASES ─────────────────────────────────

static int ev_internal_state;
extern const struct ev_loop *ev_default_loop;

// ── 29. ABI PADDING / LAYOUT STRESS ──────────────────────────────────────────
// Classic alignment/padding layout: char + int + char.

struct ev_pad {
    char a;
    int b;
    char c;
};

// ── 30. ANONYMOUS UNION INSIDE STRUCT ────────────────────────────────────────
// C11 supports anonymous unions (also accepted by common compilers in C mode).

struct ev_event {
    int type;
    union {
        int fd;
        void *ptr;
    };
};

#endif

// Broad supported stress fixture for parser + emitter regression coverage.

#ifndef STRESS_NORMAL_INPUT_H
#define STRESS_NORMAL_INPUT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define EV_VERSION_MAJOR 4
#define EV_VERSION_MINOR 33
#define EV_MAXPRI 9
#define EV_FLAG_AUTO 0x00000001u
#define EV_FLAG_DYNAMIC 0x00000002u
#define EV_FLAG_MASK 0x0000FFFFu

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

#define EV_TYPE int
typedef EV_TYPE ev_dynamic_t;

static int ev_internal_state;
extern const struct ev_loop *ev_default_loop;

struct ev_pad {
    char a;
    int b;
    char c;
};

#endif

enum {
    AC_MODE_READ = 1,
    AC_MODE_WRITE = 2
};

typedef struct anon_packet {
    int kind;
    union {
        int fd;
        void *ptr;
    };
    struct {
        unsigned short lo;
        unsigned short hi;
    } parts;
} anon_packet;

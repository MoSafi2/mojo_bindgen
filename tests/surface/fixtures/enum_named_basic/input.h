#include <stdint.h>

typedef enum enb_mode {
    ENB_ADD = 1,
    ENB_SUB = 2
} enb_mode;

enb_mode enb_flip(enb_mode mode);

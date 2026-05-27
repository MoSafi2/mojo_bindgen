#include <stdint.h>

typedef enum tag_name {
    TAG_A = 3
} typedef_name;

enum mode_tag {
    MODE_A = 1
};

typedef_name take_typedef_name(typedef_name mode);
enum mode_tag get_mode_tag(void);

#include <stdint.h>

struct ag_plain {
    char tag;
    int value;
};

_Alignas(32) struct ag_alignas_record {
    char tag;
    int value;
};

struct __attribute__((aligned(16))) ag_explicit_align {
    char tag;
    int value;
};

struct ag_alignas_field {
    char tag;
    _Alignas(32) int value;
};

struct ag_field_align {
    char tag;
    int value __attribute__((aligned(16)));
};

struct __attribute__((packed)) ag_packed {
    uint8_t tag;
    uint32_t size;
};

struct __attribute__((packed, aligned(16))) ag_packed_aligned {
    uint8_t tag;
    uint32_t size;
};

#pragma pack(push, 1)
struct ag_pragma_packed {
    uint8_t tag;
    uint32_t size;
};
#pragma pack(pop)

#pragma pack(push, 2)
struct ag_pragma_pack2 {
    char tag;
    int value;
};
#pragma pack(pop)

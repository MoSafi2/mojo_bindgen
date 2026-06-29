#include <stdint.h>

struct nft_packet_tail {
    uint32_t len;
    unsigned char payload[];
};

struct nft_packet_wrapper {
    uint32_t tag;
    struct nft_packet_tail tail;
};

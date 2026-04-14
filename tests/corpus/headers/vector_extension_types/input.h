typedef float vet_float4 __attribute__((vector_size(16)));

struct vet_payload {
    vet_float4 lanes;
};

#pragma once
struct NativeNode { struct NativeNode *next; int value; };
typedef int (*NativeCallback)(int value);
int native_accept(struct NativeNode *node, NativeCallback callback);
#define NATIVE_WIDE (1ULL << 63)

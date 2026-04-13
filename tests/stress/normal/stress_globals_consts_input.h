// Stress fixture focused on globals and constant-like declarations.

#ifndef STRESS_GLOBALS_CONSTS_INPUT_H
#define STRESS_GLOBALS_CONSTS_INPUT_H

#include <stdint.h>

struct cfg;

extern int global_counter;
extern const char *global_name;
extern const struct cfg *global_cfg;

#define DEFAULT_LIMIT 42u
#define LIB_NAME "bindgen"
#define NULL_HANDLE ((void *)0)
#define DEFAULT_ALIAS DEFAULT_LIMIT

#endif

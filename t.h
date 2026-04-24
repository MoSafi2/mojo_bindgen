// logger.h

typedef void (*log_callback_t)(const char *msg);

typedef struct logger_config {
    int level;
    log_callback_t callback;
} logger_config;

int init_logger(const logger_config *config);
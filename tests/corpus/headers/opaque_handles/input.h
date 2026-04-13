struct foo;
union bar;

typedef struct foo foo_t;

foo_t *open_foo(void);
union bar *peek_bar(foo_t *value);

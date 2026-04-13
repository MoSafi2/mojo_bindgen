struct payload {
    unsigned len;
    char data[];
};

struct holder {
    int values[4];
};

int take_ptr_to_array(int (*p)[4]);

struct ofp_handle;

struct ofp_handle *ofp_open(void);
void ofp_close(struct ofp_handle *handle);

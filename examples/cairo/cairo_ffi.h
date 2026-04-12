/*
 * Reference header for editors and C tooling: includes system Cairo.
 *
 * Do *not* pass this file to mojo-bindgen as the primary header. The generator
 * only walks top-level declarations in the primary file; a wrapper that only
 * #include's <cairo/cairo.h> yields an empty binding because the API lives in
 * cairo/cairo.h. Use ./generate.sh, which invokes mojo-bindgen on the system
 * cairo.h path.
 */
#include <cairo/cairo.h>

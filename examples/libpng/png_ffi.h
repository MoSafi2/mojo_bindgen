/*
 * Reference header for editors and C tooling: includes system libpng.
 *
 * Do *not* pass this file to mojo-bindgen as the primary header. The generator
 * only walks top-level declarations in the primary file; a wrapper that only
 * #include's <png.h> yields an empty binding because the API lives in png.h.
 * Use ./generate.sh, which invokes mojo-bindgen on the system png.h path.
 */
#include <png.h>

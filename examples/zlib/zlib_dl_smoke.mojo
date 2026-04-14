# Smoke test for OwnedDLHandle bindings: dynamic load of libz and runtime FFI calls.
# Requires zlib_bindings_dl.mojo from generate.sh (--linking owned_dl_handle).
from zlib_bindings_dl import (
    Z_OK,
    compressBound,
    gzclose,
    gzgetc,
    gzopen,
    gzputc,
    zlibCompileFlags,
    zlibVersion,
)


def _cstr(s: StaticString) -> UnsafePointer[Int8, ImmutExternalOrigin]:
    return rebind[UnsafePointer[Int8, ImmutExternalOrigin]](s.unsafe_ptr())


def main() raises:
    var version_ptr = zlibVersion()
    if not version_ptr:
        raise Error("zlibVersion returned null")

    var bound_0 = compressBound(0)
    var bound_256 = compressBound(256)
    var bound_1024 = compressBound(1024)
    if bound_0 <= 0:
        raise Error("compressBound(0) must be positive")
    if bound_1024 < bound_256:
        raise Error("compressBound should be monotonic for larger payloads")

    print("zlib.version_ptr_nonnull|", 1)
    print("zlib.compress_bound_0|", bound_0)
    print("zlib.compress_bound_256|", bound_256)
    print("zlib.compress_bound_1024|", bound_1024)
    print("zlib.compile_flags|", zlibCompileFlags())

    var payload = "hello-zlib-ffi-roundtrip"
    var writer = gzopen(_cstr("/tmp/mojo_bindgen_zlib_smoke.gz"), _cstr("wb"))
    if not writer:
        raise Error("gzopen(wb) failed")

    for cp in payload.codepoints():
        if gzputc(writer, Int32(Int(cp))) < 0:
            _ = gzclose(writer)
            raise Error("gzputc failed")

    if gzclose(writer) != Z_OK:
        raise Error("gzclose(writer) failed")

    var reader = gzopen(_cstr("/tmp/mojo_bindgen_zlib_smoke.gz"), _cstr("rb"))
    if not reader:
        raise Error("gzopen(rb) failed")

    for cp in payload.codepoints():
        var c = gzgetc(reader)
        if c < 0:
            _ = gzclose(reader)
            raise Error("gzgetc hit EOF too early")
        if c != Int32(Int(cp)):
            _ = gzclose(reader)
            raise Error("zlib file round-trip mismatch")

    if gzgetc(reader) >= 0:
        _ = gzclose(reader)
        raise Error("gzip stream longer than expected")

    if gzclose(reader) != Z_OK:
        raise Error("gzclose(reader) failed")

    print("zlib.file_roundtrip_ok|", 1)

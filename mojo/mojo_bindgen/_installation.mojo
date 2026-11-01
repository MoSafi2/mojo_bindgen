"""Relocatable runtime discovery for the distributed Linux executable."""
from std.ffi import external_call, c_int
from std.os import getenv
from std.pathlib import Path


def installation_root() -> String:
    var link = String("/proc/self/exe\0")
    var buffer = List[UInt8](length=4097, fill=0)
    var count = external_call["readlink", Int](link.unsafe_ptr(), buffer.unsafe_ptr(), 4096)
    if count <= 0 or count >= 4096:
        return ""
    var executable = String(unsafe_from_utf8_ptr=buffer.unsafe_ptr())
    var directory = String(executable[byte = 0 : executable.rfind("/")])
    return String(directory[byte = 0 : directory.rfind("/")])


def _set_environment(name: String, value: String) raises:
    var key = name + "\0"
    var text = value + "\0"
    if external_call["setenv", c_int](key.unsafe_ptr(), text.unsafe_ptr(), c_int(1)) != 0:
        raise Error("unable to configure packaged runtime: " + name)


def configure_installation() raises:
    var root = installation_root()
    if not root or not Path(root + "/manifest.json").is_file():
        # Source-built unit drivers use the SDK selected by their caller.
        return
    if not getenv("MOJO_BINDGEN_CLANG_LIBRARY_PATH"):
        var package = String(root[byte = 0 : root.rfind("/")])
        var site = String(package[byte = 0 : package.rfind("/")])
        var python = String(site[byte = 0 : site.rfind("/")])
        var lib = String(python[byte = 0 : python.rfind("/")])
        for candidate in [site + "/clang/native/libclang.so", lib + "/libclang.so"]:
            if Path(candidate).is_file():
                _set_environment("MOJO_BINDGEN_CLANG_LIBRARY_PATH", candidate)
                break
    _set_environment("MOJO_BINDGEN_CLANG_RESOURCE_DIR", root + "/lib/clang/18")

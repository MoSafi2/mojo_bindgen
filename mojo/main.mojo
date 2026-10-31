"""Native command entry point; header generation arrives in the frontend stage."""

from std.sys import argv


def main() raises:
    var args = argv()
    if len(args) == 2 and args[1] == "--version":
        print("mojo-bindgen-mojo 0.3.5 (Mojo 1.3.0.dev2026103105; type-mapping slice)")
        return
    if len(args) == 1 or (len(args) == 2 and (args[1] == "--help" or args[1] == "-h")):
        print("mojo-bindgen-mojo: native Mojo bindgen")
        print("Available: --help, --version. The native library currently provides type mapping.")
        print("Use mojo-bindgen for C header generation during the transition.")
        return
    raise Error("native header generation is not available yet; use mojo-bindgen")

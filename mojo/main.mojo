"""Public Mojo executable used directly or through the Python CLI facade."""
from std.sys import argv
from std.ffi import external_call, c_int
from mojo_bindgen.cli import run_cli
from mojo_bindgen._installation import configure_installation


def main() raises:
    configure_installation()
    var args = List[String]()
    for arg in argv():
        args.append(String(arg))
    var code = run_cli(args)
    external_call["exit", NoneType](c_int(code))

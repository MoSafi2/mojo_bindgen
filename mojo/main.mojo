"""Native header-to-binding command, alongside Python during the transition."""
from std.sys import argv
from std.ffi import external_call, c_int
from mojo_bindgen.cli import run_cli


def main():
    var args = List[String]()
    for arg in argv():
        args.append(String(arg))
    var code = run_cli(args)
    external_call["exit", NoneType](c_int(code))

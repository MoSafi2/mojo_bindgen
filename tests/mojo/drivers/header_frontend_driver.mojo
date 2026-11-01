"""Standalone test boundary: native Clang parsing to current-model CIR JSON."""
from std.sys import argv
from std.pathlib import Path
from mojo_bindgen.parsing.parser import ClangParser
from mojo_bindgen.serde import dumps_cir


def main() raises:
    var args = argv()
    var flags = List[String]()
    for i in range(3, len(args)):
        flags.append(args[i].copy())
    var unit = ClangParser(args[1], "testlib", "testlib", flags.copy()).run()
    Path(args[2]).write_text(dumps_cir(unit))

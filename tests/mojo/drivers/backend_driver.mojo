"""Test-only JSON transport around native production passes."""
from std.sys import argv
from std.memory import ArcPointer
from mojo_bindgen._debug_json import JSON, dump_json, parse_json
from operations import run_operation


def main() raises:
    var args = argv()
    var text: String
    with open(args[1], "r") as f:
        text = f.read()
    var requests = parse_json(text)
    for req in requests.items():
        try:
            print(dump_json(run_operation(req.ptr()[])))
        except error:
            var response = Dict[String, ArcPointer[JSON]]()
            response["error"] = ArcPointer(JSON.string(String(error)))
            print(dump_json(JSON.object(response^)))

"""Batch JSON driver for differential tests; this is not a generator dependency."""

from std.memory import ArcPointer
from std.sys import argv
from mojo_bindgen._debug_json import JSON, parse_json, dump_json
from mojo_bindgen.serde import (
    decode_c_type,
    decode_mojo_type,
    encode_c_type,
    encode_mojo_type,
    decode_target_abi,
)
from mojo_bindgen.type_mapping import MapTypePass, TargetQueries


def main() raises:
    var args = argv()
    if len(args) != 2:
        raise Error("expected a JSON request file")
    var text: String
    with open(args[1], "r") as stream:
        text = stream.read()
    var requests = parse_json(text)
    for request in requests.items():
        var response = Dict[String, ArcPointer[JSON]]()
        try:
            var action = request.ptr()[].get("action").ptr()[].text()
            if action == "mojo-roundtrip":
                var mapped = decode_mojo_type(request.ptr()[].get("type").ptr()[])
                response["mapped"] = ArcPointer(encode_mojo_type(mapped))
            elif action == "map" or action == "c-roundtrip":
                var source = decode_c_type(request.ptr()[].get("type").ptr()[])
                response["source"] = ArcPointer(encode_c_type(source))
                if action == "map":
                    var abi = decode_target_abi(request.ptr()[].get("target_abi").ptr()[])
                    var mapper = MapTypePass(TargetQueries(abi^))
                    response["mapped"] = ArcPointer(encode_mojo_type(mapper.run(source)))
            else:
                raise Error("unknown driver action")
        except error:
            response = Dict[String, ArcPointer[JSON]]()
            response["error"] = ArcPointer(JSON.string(String(error)))
        print(dump_json(JSON.object(response^)))

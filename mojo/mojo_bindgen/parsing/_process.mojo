"""Checked capture for compiler probes; shell arguments are always quoted."""
from std.sys._libc import popen, pclose, free
from std.ffi import external_call, c_char
from std.memory.unsafe_pointer import unsafe_cast
from std.collections import Span


def shell_quote(text: String) raises -> String:
    if "\0" in text:
        raise Error("NUL in subprocess argument")
    return "'" + text.replace("'", "'\"'\"'") + "'"


def command_output(
    args: List[String], input: Optional[String] = {}, *, quiet: Bool = False
) raises -> String:
    var command = String()
    for arg in args:
        if command:
            command += " "
        command += shell_quote(arg)
    if input:
        command = "printf %s " + shell_quote(input.value()) + " | " + command
    if quiet:
        command += " 2>/dev/null"
    var mode = String("r")
    var handle = popen(command.as_c_string_span(), mode.as_c_string_span())
    if not handle:
        raise Error("unable to execute compiler command")
    var capacity = Int(0)
    var line = Optional[Pointer[c_char, MutUntrackedOrigin]]()
    var output = String()
    var closed = False
    try:
        while True:
            var count = external_call["getline", Int](
                Pointer(to=line), Pointer(to=capacity), handle
            )
            if count < 0:
                break
            output += StringSlice(
                from_utf8=Span(unsafe_ptr=line.value().unsafe_bitcast[UInt8](), length=count)
            )
        var status = pclose(handle)
        closed = True
        if status != 0:
            raise Error("compiler command failed: " + command)
        return output^
    finally:
        if line:
            free(line.value().unsafe_bitcast[NoneType]())
        if not closed:
            _ = pclose(handle)

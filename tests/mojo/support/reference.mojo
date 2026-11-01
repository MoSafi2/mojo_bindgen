"""Frozen Python-reference vectors checked by native APIs and TestSuite assertions."""
from std.memory import ArcPointer
from std.os import getenv
from std.pathlib import Path
from mojo_bindgen._debug_json import JSON, parse_json, dump_json
from operations import run_operation
from std.testing import assert_equal, assert_true
from mojo_bindgen.serde import loads_cir, loads_mojo_ir
from mojo_bindgen.orchestrator import generate_from_unit
from mojo_bindgen.codegen.mojo_ir_printer import render_mojo_module
from operations import _options
from mojo_bindgen.analysis.common import strip_whitespace


def read_json(path: String) raises -> JSON:
    with open(path, "r") as file:
        return parse_json(file.read())


def write_json(path: String, value: JSON) raises:
    with open(path, "w") as file:
        file.write(dump_json(value))


def case_root(relative: String) -> String:
    var leaf = String(relative[byte = relative.rfind("/") + 1 :])
    return getenv("BINDGEN_TEST_WORK") + "/" + String(leaf[byte = 0 : leaf.find(".")])


def expand(text: String, work: String) -> String:
    return text.replace("@ROOT@", getenv("BINDGEN_TEST_ROOT")).replace("@WORK@", work)


def expanded(value: JSON, work: String) raises -> JSON:
    match value:
        case .string(v):
            return JSON.string(expand(v, work))
        case .array(v):
            var result = List[ArcPointer[JSON]]()
            for item in v:
                result.append(ArcPointer(expanded(item.ptr()[], work)))
            return JSON.array(result^)
        case .object(v):
            var result = Dict[String, ArcPointer[JSON]]()
            for item in v.items():
                result[item.key] = ArcPointer(expanded(item.value.ptr()[], work))
            return JSON.object(result^)
        case _:
            return value.copy()


def equivalent(actual: JSON, expected: JSON) raises -> Bool:
    # Object order is not part of debug JSON. Paths were expanded before comparing;
    # declaration identities and literal strings still have to match exactly.
    match expected:
        case .object(fields):
            match actual:
                case .object(found):
                    if len(fields) != len(found):
                        return False
                    for item in fields.items():
                        if item.key not in found or not equivalent(
                            found[item.key].ptr()[], item.value.ptr()[]
                        ):
                            return False
                    return True
                case _:
                    return False
        case .array(values):
            match actual:
                case .array(found):
                    if len(values) != len(found):
                        return False
                    for i in range(len(values)):
                        if not equivalent(found[i].ptr()[], values[i].ptr()[]):
                            return False
                    return True
                case _:
                    return False
        case .string(text):
            match actual:
                case .string(found):
                    return text == found
                case _:
                    return False
        case _:
            return dump_json(actual) == dump_json(expected)


def prepare_case(relative: String) raises:
    var work = case_root(relative)
    var fixture = expanded(read_json(work + "/fixture.json"), work)
    var results = List[ArcPointer[JSON]]()
    for operation in fixture.get("operations").ptr()[].items():
        try:
            results.append(ArcPointer(run_operation(operation.ptr()[].get("request").ptr()[])))
        except error:
            var fields = Dict[String, ArcPointer[JSON]]()
            fields["error"] = ArcPointer(JSON.string(String(error)))
            results.append(ArcPointer(JSON.object(fields^)))
    for item in fixture.get("writes").ptr()[].items():
        var op = item.ptr()[].get("operation").ptr()[].int_value()
        var key = item.ptr()[].get("key").ptr()[].text()
        var source = results[op].ptr()[].get(key).ptr()[].text()
        var path = work + "/" + item.ptr()[].get("path").ptr()[].text()
        with open(path, "w") as file:
            file.write(source)
    write_json(work + "/operations.json", JSON.array(results^))
    write_json(work + "/plan.json", fixture.get("steps").ptr()[])


def check_case(relative: String) raises:
    var work = case_root(relative)
    var fixture = expanded(read_json(work + "/fixture.json"), work)
    var actual = read_json(work + "/operations.json").items()
    var operations = fixture.get("operations").ptr()[].items()
    assert_equal(len(actual), len(operations))
    for i in range(len(operations)):
        var op = operations[i].ptr()[].copy()
        if op.has("expected_error"):
            assert_true(actual[i].ptr()[].has("error"), "expected rejected operation " + String(i))
            if fixture.has("operation_error_contains"):
                var error = actual[i].ptr()[].get("error").ptr()[].text()
                for token in fixture.get("operation_error_contains").ptr()[].items():
                    assert_true(token.ptr()[].text() in error, "missing rejection diagnostic")
            continue
        var expected = op.get("expected")
        match expected.ptr()[]:
            case .object(fields):
                for item in fields.items():
                    assert_true(actual[i].ptr()[].has(item.key), "missing response " + item.key)
                    var found = actual[i].ptr()[].get(item.key)
                    if not equivalent(found.ptr()[], item.value.ptr()[]):
                        with open(work + "/actual.json", "w") as file:
                            file.write(dump_json(found.ptr()[]))
                        raise Error(
                            "reference mismatch: "
                            + relative
                            + " operation "
                            + String(i)
                            + " "
                            + item.key
                        )
            case _:
                raise Error("invalid expected response")
    var expected_steps = fixture.get("steps").ptr()[].items()
    var steps = read_json(work + "/processes.json").items()
    assert_equal(len(steps), len(expected_steps))
    for i in range(len(steps)):
        var got = steps[i].ptr()[].copy()
        var expected = expected_steps[i].ptr()[].copy()
        var code = got.get("returncode").ptr()[].int_value()
        var wanted = expected.get("returncode").ptr()[].int_value()
        assert_equal(code == 0, wanted == 0, relative + " phase " + String(i))
        var stdout = got.get("stdout").ptr()[].text()
        var stderr = got.get("stderr").ptr()[].text()
        if expected.has("exact_code"):
            assert_equal(code, wanted, relative + " phase exit code " + String(i))
        if expected.has("stdout_json_values"):
            var actual_values = List[String]()
            for value in parse_json(stdout).items():
                actual_values.append(value.ptr()[].text())
            for value in expected.get("stdout_json_values").ptr()[].items():
                assert_true(value.ptr()[].text() in actual_values)
        if expected.has("stdout_contains"):
            for token in expected.get("stdout_contains").ptr()[].items():
                assert_true(
                    token.ptr()[].text() in stdout, "missing stdout marker " + token.ptr()[].text()
                )
        if code == 0 and expected.has("expected_values"):
            var values = Dict[String, String]()
            for line in stdout.split("\n"):
                var sep = line.find("|")
                if sep >= 0:
                    values[strip_whitespace(String(line[byte=0:sep]))] = strip_whitespace(
                        String(line[byte = sep + 1 :])
                    )
            match expected.get("expected_values").ptr()[]:
                case .object(fields):
                    assert_equal(len(values), len(fields))
                    for entry in fields.items():
                        assert_true(entry.key in values, "missing runtime value " + entry.key)
                        var found = parse_json(values[entry.key])
                        match entry.value.ptr()[]:
                            case .integer(v):
                                assert_equal(found.integer_value().digits, v.digits, entry.key)
                            case .floating(v):
                                var difference = found.float_value() - v
                                if difference < 0:
                                    difference = -difference
                                var magnitude = v if v >= 0 else -v
                                assert_true(difference <= max(1e-12, magnitude * 1e-12), entry.key)
                            case _:
                                raise Error("invalid numeric runtime expectation")
                case _:
                    raise Error("invalid runtime values")
        if code == 0 and expected.has("stdout") and expected.has("strip_stdout"):
            assert_equal(
                strip_whitespace(stdout),
                strip_whitespace(expected.get("stdout").ptr()[].text()),
                relative,
            )
        elif code == 0 and expected.has("stdout"):
            assert_equal(
                stdout,
                expected.get("stdout").ptr()[].text(),
                relative + " phase stdout " + String(i),
            )
        if code != 0 and fixture.has("diagnostic_any"):
            var matched = False
            for token in fixture.get("diagnostic_any").ptr()[].items():
                matched = matched or token.ptr()[].text() in stdout + stderr
            assert_true(matched, "missing source-level compiler rejection")
        if code != 0 and fixture.has("diagnostics"):
            for token in fixture.get("diagnostics").ptr()[].items():
                assert_true(
                    token.ptr()[].text() in stdout + stderr,
                    "missing expected diagnostic " + token.ptr()[].text(),
                )

    if fixture.has("file_checks"):
        for check in fixture.get("file_checks").ptr()[].items():
            var path = check.ptr()[].get("path").ptr()[].text()
            assert_equal(
                Path(path).is_file(), check.ptr()[].get("exists").ptr()[].bool_value(), path
            )
            if check.ptr()[].has("exact"):
                assert_equal(read_text(path), check.ptr()[].get("exact").ptr()[].text(), path)
            if check.ptr()[].has("contains"):
                var contents = read_text(path)
                for token in check.ptr()[].get("contains").ptr()[].items():
                    assert_true(token.ptr()[].text() in contents, path)
    if fixture.has("diagnostic_file"):
        var entries = read_json(fixture.get("diagnostic_file").ptr()[].text()).items()
        assert_true(len(entries) > 0)
        assert_equal(entries[0].ptr()[].get("stage").ptr()[].text(), "frontend")
        assert_equal(entries[0].ptr()[].get("severity").ptr()[].text(), "warning")
        assert_true("no prototype" in entries[0].ptr()[].get("message").ptr()[].text())
    if fixture.has("example_module"):
        var module_name = fixture.get("example_module").ptr()[].text()
        var unit = loads_cir(read_text(work + "/cir.json"))
        var module = loads_mojo_ir(read_text(work + "/mojo.json"))
        var generated = generate_from_unit(unit, _options(fixture), module_name.copy())
        var emitted = read_text(work + "/" + module_name + ".mojo")
        assert_equal(generated.bindings_source, emitted)
        assert_equal(render_mojo_module(module), emitted)
        assert_equal(generated.layout_test_source.value(), read_text(work + "/layout.mojo"))


def read_text(path: String) raises -> String:
    with open(path, "r") as file:
        return file.read()

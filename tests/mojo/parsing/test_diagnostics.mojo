# Tests for parser diagnostic collection and normalization.
# Ported from the diagnostics coverage in tests/unit/test_parsing_registry.py

from std.testing import assert_equal, assert_true, TestSuite
from mojo.parsing.frontend import (
    FrontendDiagnostic,
    ClangFrontend,
    ClangFrontendConfig,
)
from mojo.parsing.diagnostics import ParserDiagnosticSink

comptime _FIXTURES = "tests/mojo/parsing/fixtures"


def test_frontend_diagnostic_str() raises:
    var d = FrontendDiagnostic(
        severity="error",
        file="test.h",
        line=10,
        col=5,
        message="expected ';' after struct",
    )
    assert_equal(String(d), "test.h:10:5: error: expected ';' after struct")


def test_sink_collects_frontend_diagnostics() raises:
    var sink = ParserDiagnosticSink()
    var diags: List[FrontendDiagnostic] = [
        FrontendDiagnostic(
            severity="warning", file="a.h", line=1, col=1, message="unused"
        ),
        FrontendDiagnostic(
            severity="error", file="b.h", line=2, col=3, message="bad type"
        ),
    ]
    sink.add_frontend_diagnostics(diags)
    assert_equal(len(sink.diagnostics), 2)


def test_sink_to_ir_diagnostics() raises:
    var sink = ParserDiagnosticSink()
    sink.add_frontend_diagnostics(
        [
            FrontendDiagnostic(
                severity="error", file="a.h", line=1, col=2, message="oops"
            ),
        ]
    )
    var ir = sink.to_ir_diagnostics()
    assert_equal(len(ir), 1)
    assert_equal(ir[0].severity, "error")
    assert_equal(ir[0].message, "oops")
    assert_true(ir[0].file.value() == "a.h")
    assert_true(ir[0].line.value() == 1)
    assert_true(ir[0].col.value() == 2)


def test_clang_parser_collects_no_fatal_diags_for_clean_header() raises:
    var header = "/home/mmabrouk/mojo_bindgen/" + _FIXTURES + "/probe.h"
    var frontend = ClangFrontend(
        ClangFrontendConfig(
            header=header,
            compile_args=List[String](),
            include_headers=List[String](),
        )
    )
    var tu = frontend.parse_translation_unit()
    var diags = frontend.collect_diagnostics(tu)
    # Clean header should have no fatal diagnostics
    var has_fatal = False
    for d in diags:
        if d.severity == "error" or d.severity == "fatal":
            has_fatal = True
    assert_true(not has_fatal)


def main() raises:
    var suite = TestSuite.discover_tests[__functions_in_module()]().run()

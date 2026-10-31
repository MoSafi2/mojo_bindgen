"""Compile and execute the Mojo 1.2 FFI upgrade against a real C library."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from mojo_bindgen import BindgenOptions, bindgen

pytestmark = pytest.mark.skipif(
    not shutil.which("mojo") or not shutil.which("cc"), reason="requires Mojo and a C compiler"
)

HEADER = """
int mf_sum(int count, ...);
void mf_record(int count, ...);
double mf_values(int count, ...);
double mf_mix(int tag, ...);
int mf_value(void);
int mf_missing(void);
extern int mf_counter;
extern const int mf_limit;
typedef struct __attribute__((aligned(32))) MFAligned { double x; } MFAligned;
double mf_aligned_sum(const MFAligned *values);
int mf_aligned_ok(const MFAligned *values);
"""

SOURCE = """
#include "modern.h"
#include <stdarg.h>
#include <stdint.h>
#ifndef MF_VALUE
#define MF_VALUE 7
#endif
int mf_counter = 3;
const int mf_limit = 13;
int mf_value(void) { return MF_VALUE; }
int mf_sum(int count, ...) {
    va_list args; va_start(args, count); int result = 0;
    for (int i=0; i<count; ++i) result += va_arg(args, int);
    va_end(args); return result;
}
double mf_values(int count, ...) {
    va_list args; va_start(args, count); double result = 0;
    for (int i=0; i<count; ++i) result += va_arg(args, double);
    va_end(args); return result;
}
void mf_record(int count, ...) {
    va_list args; va_start(args, count); mf_counter = 0;
    for (int i=0; i<count; ++i) mf_counter += va_arg(args, int);
    va_end(args);
}
double mf_mix(int tag, ...) {
    va_list args; va_start(args, tag);
    int i = va_arg(args, int); double d = va_arg(args, double);
    int *p = va_arg(args, int *); va_end(args);
    return tag + i + d + (p ? *p : 0);
}
double mf_aligned_sum(const MFAligned *v) { return v[0].x + v[1].x + v[2].x; }
int mf_aligned_ok(const MFAligned *v) {
    return ((uintptr_t)&v[0] % 32 == 0) && ((uintptr_t)&v[1] % 32 == 0)
        && ((uintptr_t)&v[2] % 32 == 0) && sizeof(MFAligned) == 32;
}
"""


def _run(command: list[str], *, env=None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, env=env, timeout=60)


@pytest.fixture(scope="module")
def ffi_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("mojo12")
    header = root / "modern.h"
    header.write_text(HEADER)
    source = root / "modern.c"
    source.write_text(SOURCE)
    for name, value in (("modernffi", 7), ("override", 11)):
        result = _run(
            [
                "cc",
                "-shared",
                "-fPIC",
                str(source),
                f"-DMF_VALUE={value}",
                "-o",
                str(root / f"lib{name}.so"),
            ]
        )
        assert result.returncode == 0, result.stderr
    for mode, module in (
        ("external_call", "modern_external"),
        ("owned_dl_handle", "modern_dynamic"),
    ):
        result = bindgen(
            BindgenOptions(
                header=header,
                library="modernffi",
                link_name="modernffi",
                linking=mode,
                library_path_hint=str(root / "libmodernffi.so"),
            )
        )
        (root / f"{module}.mojo").write_text(result.bindings_source)
    return root


def _build(root: Path, name: str, source: str, *, direct=False):
    path = root / f"{name}.mojo"
    path.write_text(source)
    command = ["mojo", "build", "--Werror", str(path), "-I", str(root), "-o", str(root / name)]
    if direct:
        command += ["-Xlinker", f"-L{root}", "-Xlinker", "-lmodernffi"]
    return _run(command)


def _environment(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(root) + ":" + env.get("LD_LIBRARY_PATH", "")
    env.pop("MOJO_BINDGEN_MODERNFFI_LIBRARY_PATH", None)
    env.pop("MOJO_BINDGEN_LIBRARY_PATH", None)
    return env


def test_checked_varargs_and_overaligned_array(ffi_root: Path) -> None:
    source = """from modern_external import mf_sum, mf_record, mf_counter, mf_values, mf_mix, MFAligned, mf_aligned_sum, mf_aligned_ok
from std.ffi import c_int
from std.testing import assert_equal

def main() raises:
    assert_equal(mf_sum(c_int(0)), c_int(0))
    mf_record(c_int(0))
    assert_equal(mf_counter.load(), c_int(0))
    mf_record(c_int(2), c_int(3), c_int(5))
    assert_equal(mf_counter.load(), c_int(8))
    assert_equal(mf_sum(c_int(3), c_int(2), c_int(3), c_int(4)), c_int(9))
    assert_equal(mf_values(c_int(1), Float64(1.25)), Float64(1.25))
    assert_equal(mf_values(c_int(2), Float64(1.25), Float64(2.5)), Float64(3.75))
    var value = c_int(6)
    assert_equal(mf_mix(c_int(1), c_int(2), Float64(0.5), Pointer(to=value)), Float64(9.5))
    var ptr = Optional(Pointer(to=value))
    assert_equal(mf_mix(c_int(1), c_int(2), Float64(0.5), ptr), Float64(9.5))
    var null_ptr = Optional[Pointer[c_int, MutUntrackedOrigin]](None)
    assert_equal(mf_mix(c_int(1), c_int(2), Float64(0.5), null_ptr), Float64(3.5))
    var values = Array[MFAligned, 3](uninitialized=True)
    values[0].x = 1.0
    values[1].x = 2.0
    values[2].x = 3.0
    var raw = values.unsafe_ptr().as_imm().unsafe_origin_cast[ImmUntrackedOrigin]()
    assert_equal(mf_aligned_ok(raw), c_int(1))
    assert_equal(mf_aligned_sum(raw), Float64(6))
    deinit(values^)
"""
    result = _build(ffi_root, "checked", source, direct=True)
    assert result.returncode == 0, result.stderr
    result = _run([str(ffi_root / "checked")], env=_environment(ffi_root))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "call, diagnostic",
    [
        ("mf_sum()", "missing fixed C arguments"),
        ("mf_sum(Int64(1), c_int(1))", "fixed argument 0"),
        ("mf_sum(c_int(1), Int8(2))", "promote"),
        ("mf_sum(c_int(1), True)", "promote"),
        ("mf_values(c_int(1), Float32(1.25))", "promote"),
        ('mf_sum(c_int(1), String("unsafe"))', "as_c_string_span"),
        ("mf_sum(c_int(1), Optional[c_int](1))", "promote"),
    ],
)
def test_varargs_reject_unsafe_arguments(ffi_root: Path, call: str, diagnostic: str) -> None:
    result = _build(
        ffi_root,
        "invalid",
        f"from modern_external import mf_sum, mf_values\nfrom std.ffi import c_int\n\ndef main():\n    _ = {call}\n",
        direct=True,
    )
    assert result.returncode != 0
    assert diagnostic in result.stderr, result.stderr


def test_dynamic_globals_and_override_precedence(ffi_root: Path) -> None:
    source = """from modern_dynamic import mf_value, mf_counter, mf_limit
from std.ffi import c_int
from std.testing import assert_equal

def main() raises:
    assert_equal(mf_counter.load(), c_int(3))
    mf_counter.store(c_int(9))
    assert_equal(mf_counter.ptr()[], c_int(9))
    assert_equal(mf_limit.load(), c_int(13))
    print(mf_value())
"""
    result = _build(ffi_root, "dynamic", source)
    assert result.returncode == 0, result.stderr
    env = _environment(ffi_root)
    result = _run([str(ffi_root / "dynamic")], env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "7"
    env["MOJO_BINDGEN_LIBRARY_PATH"] = str(ffi_root / "liboverride.so")
    result = _run([str(ffi_root / "dynamic")], env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "11"
    env["MOJO_BINDGEN_MODERNFFI_LIBRARY_PATH"] = str(ffi_root / "libmodernffi.so")
    result = _run([str(ffi_root / "dynamic")], env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "7"


def test_missing_dynamic_symbol_keeps_non_raising_diagnostic(ffi_root: Path) -> None:
    result = _build(
        ffi_root,
        "missing",
        "from modern_dynamic import mf_missing\n\ndef main():\n    print(mf_missing())\n",
    )
    assert result.returncode == 0, result.stderr
    result = _run([str(ffi_root / "missing")], env=_environment(ffi_root))
    assert result.returncode != 0
    assert "mf_missing" in result.stdout + result.stderr
    assert "modernffi" in result.stdout + result.stderr


def test_missing_library_has_candidate_diagnostic(ffi_root: Path) -> None:
    result = bindgen(
        BindgenOptions(
            header=ffi_root / "modern.h",
            library="missing_bindgen_test_library",
            link_name="missing_bindgen_test_library",
            linking="owned_dl_handle",
            library_path_hint=str(ffi_root / "does-not-exist.so"),
        )
    )
    (ffi_root / "missing_library.mojo").write_text(result.bindings_source)
    result = _build(
        ffi_root,
        "missing_lib",
        "from missing_library import mf_value\n\ndef main():\n    print(mf_value())\n",
    )
    assert result.returncode == 0, result.stderr
    result = _run([str(ffi_root / "missing_lib")], env=_environment(ffi_root))
    assert result.returncode != 0
    assert "does-not-exist.so" in result.stdout + result.stderr
    assert "missing_bindgen_test_library" in result.stdout + result.stderr

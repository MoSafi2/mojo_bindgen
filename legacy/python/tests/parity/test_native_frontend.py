"""Direct native parsing parity; Python participates only as a test reference."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from native_testing.build import build_target

from tests.parity.test_native_types import ROOT

pytestmark = [pytest.mark.expensive, pytest.mark.integration]
NATIVE_PREFIX = ROOT / "mojo/.pixi/envs/default"


def run(command, *, env, timeout=240, cwd=ROOT):
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@dataclass
class NativeFrontend:
    binary: Path
    environment: dict[str, str] = field(repr=False)

    def __iter__(self):
        yield self.binary
        yield self.environment


def native_environment():
    env = os.environ.copy()
    env["PATH"] = str(NATIVE_PREFIX / "bin") + os.pathsep + env["PATH"]
    env["MOJO_BINDGEN_CLANG_LIBRARY_PATH"] = str(NATIVE_PREFIX / "lib/libclang.so")
    env["CONDA_PREFIX"] = str(NATIVE_PREFIX)
    return env


@pytest.fixture(scope="module", params=[0, 3], ids=["O0", "O3"])
def frontend(request):
    binary = build_target("cli", request.param)
    env = native_environment()
    return NativeFrontend(binary, env)


@pytest.fixture(scope="module")
def references(tmp_path_factory):
    directory = tmp_path_factory.mktemp("frontend-reference")
    roots = [
        "tests/corpus/headers",
        "tests/surface/fixtures",
        "tests/stress/fixtures",
        "tests/e2e/fixtures",
        "tests/surface/alignment/fixtures",
    ]
    headers = [p for root in roots for p in sorted((ROOT / root).glob("*/input.h"))]
    assert len(headers) >= 49
    env = native_environment()
    flags = ["-x", "c", "-std=gnu11", "-I/usr/include"]
    for driver in ("cc", "clang"):
        include = run([driver, "-print-file-name=include"], env=env).stdout.strip()
        if Path(include).is_dir() and "-I" + include not in flags:
            flags.append("-I" + include)
    flags.append("-fretain-comments-from-system-headers")
    requests = [{"header": str(header), "flags": flags} for header in headers]
    source, target = directory / "requests.json", directory / "expected.json"
    source.write_text(json.dumps(requests))
    run(
        [
            sys.executable,
            "-I",
            str(Path(__file__).resolve().parent / "frontend_reference.py"),
            str(source),
            str(target),
        ],
        env=os.environ.copy(),
    )
    return requests, json.loads(target.read_text())


def test_all_shared_headers_and_sources(frontend, references, tmp_path):
    binary, env = frontend
    requests, expected = references
    for request, want in zip(requests, expected, strict=True):
        for mode in ("external_call", "owned_dl_handle"):
            output = tmp_path / "bindings.mojo"
            cir, mojo_ir, layout = [
                tmp_path / name for name in ("cir.json", "mojo.json", "layout.mojo")
            ]
            # Raw args are deliberately identical for the isolated reference.
            arguments = [
                str(binary),
                request["header"],
                "--library",
                "testlib",
                "--link-name",
                "testlib",
                "--link-mode",
                mode.replace("_", "-"),
                "--dump-cir",
                str(cir),
                "--dump-mojo-ir",
                str(mojo_ir),
                "--layout-tests",
                str(layout),
                "-o",
                str(output),
                "--diagnostics",
                "silent",
            ]
            # Keep comments enabled for byte parity; the explicit flags additionally
            # override default probes without affecting Clang's effective search.
            for flag in request["flags"]:
                arguments.append("--clang-arg=" + flag)
            run(arguments, env=env)
            assert json.loads(cir.read_text()) == want["raw"], request["header"]
            assert json.loads(mojo_ir.read_text()) == want["modes"][mode]["module"]
            assert output.read_text() == want["modes"][mode]["bindings"]
            assert layout.read_text() == want["modes"][mode]["layout"]


def test_cli_errors_dumps_and_multiple_headers(frontend, tmp_path):
    binary, env = frontend
    header = tmp_path / "api.h"
    sibling = tmp_path / "extra.h"
    header.write_text("#pragma once\nstruct Node { struct Node *next; int value; };\n")
    sibling.write_text("#pragma once\nint accept(struct Node *node);\n")
    common = [str(header), "--public-header", str(sibling), "--std", "c11", "-D", "FEATURE=1"]
    output = tmp_path / "bindings.mojo"
    run(
        [str(binary), *common, "-o", str(output), "--dump-preprocessed", str(tmp_path / "pre.c")],
        env=env,
    )
    assert "accept" in output.read_text()
    assert "struct Node" in (tmp_path / "pre.c").read_text()
    args = run([str(binary), *common, "--print-clang-args"], env=env)
    assert "-DFEATURE=1" in json.loads(args.stdout)
    for arguments, code in [
        ([], 0),
        (["--help"], 0),
        (["--version"], 0),
        (["--unknown"], 2),
        (["missing.h"], 1),
    ]:
        result = subprocess.run([str(binary), *arguments], env=env, capture_output=True, text=True)
        assert result.returncode == code, result.stderr
    header.write_text("int broken = ;\n")
    output.unlink()
    result = subprocess.run(
        [str(binary), str(header), "-o", str(output)], env=env, capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "libclang reported errors" in result.stderr
    assert not output.exists()
    header.write_text("int __attribute__((ms_abi)) windows_call(int);\n")
    result = subprocess.run(
        [str(binary), str(header), "-o", str(output)], env=env, capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "unsupported calling convention 'WIN64'" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    "extra", [[], ["--target", "i386-unknown-linux-gnu"], ["--clang-arg=-funsigned-char"]]
)
def test_unicode_unsigned_enums_and_target_contexts(frontend, tmp_path, extra):
    binary, env = frontend
    header = tmp_path / "λ header.h"
    header.write_text(
        "struct naïve { char letter; long value; struct naïve *next; };\n"
        "enum Wide { WIDE_MAX = 0xffffffffffffffffULL };\n"
        "enum Bits { BIT_ONE = 1 }; struct BitHolder { enum Bits tag:1; unsigned int ok:3; };\n"
        "typedef int (*Nested)(int (*callback)(char));\n"
        "#define LARGE (1ULL << 100)\n"
        '#define ESCAPED "λ\\n"\n'
    )
    expected, actual = tmp_path / "expected.mojo", tmp_path / "actual.mojo"
    py_cir, native_cir = tmp_path / "python.json", tmp_path / "native.json"
    common = [str(header), "--library", "wide", "--link-name", "wide", *extra]
    run(
        [
            sys.executable,
            "-I",
            str(Path(__file__).resolve().parent / "frontend_reference.py"),
            "cli",
            *common,
            "-o",
            str(expected),
            "--dump-cir",
            str(py_cir),
        ],
        env=env,
    )
    run([str(binary), *common, "-o", str(actual), "--dump-cir", str(native_cir)], env=env)
    assert json.loads(py_cir.read_text()) == json.loads(native_cir.read_text())
    assert actual.read_bytes() == expected.read_bytes()


def test_diagnostics_and_warning_exit(frontend, tmp_path):
    binary, env = frontend
    header = tmp_path / "warning.h"
    header.write_text("int old();\n")
    output, diagnostic = tmp_path / "bindings.mojo", tmp_path / "diagnostics.json"
    result = subprocess.run(
        [
            str(binary),
            str(header),
            "--diagnostics",
            "json",
            "--diagnostics-output",
            str(diagnostic),
            "--warnings-as-errors",
            "-o",
            str(output),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert output.is_file()
    entries = json.loads(diagnostic.read_text())
    assert entries[0]["stage"] == "frontend"
    assert entries[0]["severity"] == "warning"
    assert "no prototype" in entries[0]["message"]

"""Real example headers: Python CLI JSON -> independent native backend -> stable FFI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from native_testing.build import build_target

from mojo_bindgen.analysis.pipeline import AnalysisOrchestrator
from mojo_bindgen.serde import dumps_cir, loads_cir
from tests.parity.test_native_frontend import frontend as frontend
from tests.parity.test_native_frontend import native_environment
from tests.parity.test_native_types import ROOT

pytestmark = [pytest.mark.expensive, pytest.mark.integration]
PREFIX = ROOT / "examples/.pixi/envs/default"


@dataclass(frozen=True)
class Example:
    name: str
    header: str
    library: str
    module: str
    smoke: str
    success: str


EXAMPLES = (
    Example(
        "zlib", "zlib.h", "z", "zlib_bindings", "zlib_dl_smoke.mojo", "zlib.file_roundtrip_ok| 1"
    ),
    Example(
        "cairo",
        "cairo/cairo.h",
        "cairo",
        "cairo_bindings",
        "cairo_smoke.mojo",
        "=== ALL TESTS PASSED ===",
    ),
    Example(
        "libpng",
        "png.h",
        "png16",
        "libpng_bindings",
        "libpng_smoke.mojo",
        "libpng.struct_api_ok| 1",
    ),
    Example(
        "sqlite",
        "sqlite3.h",
        "sqlite3",
        "sqlite3_bindings",
        "sqlite_smoke.mojo",
        "=== ALL TESTS PASSED ===",
    ),
)


def _run(command, *, env=None, cwd=ROOT, timeout=180):
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope="module")
def libraries():
    if not (PREFIX / "include/cairo/cairo.h").exists():
        pytest.skip("install locked example libraries with pixi run --locked native-example-parity")
    env = os.environ.copy()
    env["CPATH"] = str(PREFIX / "include")
    env["LD_LIBRARY_PATH"] = str(PREFIX / "lib") + ":" + env.get("LD_LIBRARY_PATH", "")
    return env


@pytest.fixture(scope="module", params=[0, 3], ids=["O0", "O3"])
def json_backend(request):
    executable = build_target("json_backend", request.param)
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = (
        str(ROOT / "mojo/.pixi/envs/default/lib") + ":" + env.get("LD_LIBRARY_PATH", "")
    )

    def run(stage, source, output, module, *options):
        # No Python process participates after the native executable starts.
        return _run([str(executable), stage, str(source), str(output), module, *options], env=env)

    return run


@pytest.fixture(scope="module")
def python_dumps(tmp_path_factory, libraries):
    directory = tmp_path_factory.mktemp("example-python-dumps")
    results = {}
    reference_env = libraries.copy()
    native_env = native_environment()
    for name in ("PATH", "CONDA_PREFIX", "MOJO_BINDGEN_CLANG_LIBRARY_PATH"):
        reference_env[name] = native_env[name]
    for example in EXAMPLES:
        for mode in ("external_call", "owned_dl_handle"):
            output = directory / example.name / mode
            output.mkdir(parents=True)
            bindings = output / f"{example.module}.mojo"
            library = str(PREFIX / f"lib/lib{example.library}.so")
            _run(
                [
                    sys.executable,
                    "-I",
                    str(Path(__file__).resolve().parent / "frontend_reference.py"),
                    "cli",
                    str(PREFIX / "include" / example.header),
                    "--library",
                    example.library,
                    "--link-name",
                    example.library,
                    "--link-mode",
                    mode.replace("_", "-"),
                    "--library-path",
                    library,
                    "--dump-cir",
                    str(output / "raw.cir.json"),
                    "--dump-mojo-ir",
                    str(output / "final.mojo_ir.json"),
                    "--layout-tests",
                    str(output / f"{example.module}_layout_tests.mojo"),
                    "--output",
                    str(bindings),
                ],
                env=reference_env,
            )
            # Expected canonical CIR is checked independently of source rendering.
            source = output / "raw.cir.json"
            normalized = AnalysisOrchestrator().normalize_cir(loads_cir(source.read_text()))
            (output / "normalized.cir.json").write_text(dumps_cir(normalized), encoding="utf-8")
            results[example.name, mode] = output
    return results


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.name)
@pytest.mark.parametrize("mode", ["external_call", "owned_dl_handle"])
def test_python_json_examples_continue_natively(
    json_backend, python_dumps, libraries, example, mode, tmp_path
):
    reference = python_dumps[example.name, mode]
    source = reference / "raw.cir.json"
    target = reference / "final.mojo_ir.json"
    source_before, target_before = source.read_bytes(), target.read_bytes()
    library = str(PREFIX / f"lib/lib{example.library}.so")
    json_backend("cir", source, tmp_path, example.module, mode, library)
    module = tmp_path / f"{example.module}.mojo"
    assert module.read_bytes() == (reference / module.name).read_bytes()
    layout = tmp_path / f"{example.module}_layout_tests.mojo"
    assert layout.read_bytes() == (reference / layout.name).read_bytes()
    assert json.loads((tmp_path / f"{example.module}.mojo_ir.json").read_text()) == json.loads(
        target_before
    )
    assert json.loads((tmp_path / f"{example.module}.cir.json").read_text()) == json.loads(
        (reference / "normalized.cir.json").read_text()
    )
    # The other stage can be consumed directly too; use an independent output path.
    emitted = tmp_path / "from-mojo-ir"
    emitted.mkdir()
    json_backend("mojo-ir", target, emitted, example.module)
    assert (emitted / module.name).read_bytes() == module.read_bytes()
    assert json.loads((emitted / f"{example.module}.mojo_ir.json").read_text()) == json.loads(
        target_before
    )
    assert source.read_bytes() == source_before
    assert target.read_bytes() == target_before
    _exercise_bindings(example, mode, libraries, tmp_path, module)


def _exercise_bindings(example, mode, libraries, tmp_path, module):
    binary = tmp_path / "smoke"
    # Import beside the fresh bindings, never beside ignored stale example output.
    smoke = tmp_path / example.smoke
    smoke.write_text(
        (ROOT / "examples" / example.name / example.smoke).read_text(), encoding="utf-8"
    )
    command = [
        "mojo",
        "build",
        "--Werror",
        str(smoke),
        "-I",
        str(tmp_path),
        "-o",
        str(binary),
    ]
    if mode == "external_call":
        command += ["-Xlinker", f"-L{PREFIX / 'lib'}", "-Xlinker", f"-l{example.library}"]
    _run(command, env=libraries)
    # Existing smoke programs write files; isolate their working directory.
    result = _run([str(binary)], env=libraries, cwd=tmp_path)
    assert example.success in result.stdout, result.stdout


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda e: e.name)
@pytest.mark.parametrize("mode", ["external_call", "owned_dl_handle"])
def test_native_headers_generate_examples(
    frontend, python_dumps, libraries, example, mode, tmp_path
):
    reference = python_dumps[example.name, mode]
    env = frontend.environment.copy()
    env["CPATH"] = libraries["CPATH"]
    env["LD_LIBRARY_PATH"] = libraries["LD_LIBRARY_PATH"]
    module = tmp_path / f"{example.module}.mojo"
    layout = tmp_path / f"{example.module}_layout_tests.mojo"
    cir, mojo_ir = tmp_path / "raw.json", tmp_path / "mojo.json"
    _run(
        [
            str(frontend.binary),
            str(PREFIX / "include" / example.header),
            "--library",
            example.library,
            "--link-name",
            example.library,
            "--link-mode",
            mode.replace("_", "-"),
            "--library-path",
            str(PREFIX / f"lib/lib{example.library}.so"),
            "--output",
            str(module),
            "--layout-tests",
            str(layout),
            "--dump-cir",
            str(cir),
            "--dump-mojo-ir",
            str(mojo_ir),
        ],
        env=env,
    )
    assert module.read_bytes() == (reference / module.name).read_bytes()
    assert layout.read_bytes() == (reference / layout.name).read_bytes()
    assert json.loads(cir.read_text()) == json.loads((reference / "raw.cir.json").read_text())
    assert json.loads(mojo_ir.read_text()) == json.loads(
        (reference / "final.mojo_ir.json").read_text()
    )
    _exercise_bindings(example, mode, libraries, tmp_path, module)

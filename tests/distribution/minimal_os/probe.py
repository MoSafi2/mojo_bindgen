"""Installed-product assertions inside a container without the source checkout."""

from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run(arguments, *, success=True, env=None):
    result = subprocess.run(arguments, text=True, capture_output=True, env=env, timeout=120)
    print(f"$ {' '.join(map(str, arguments))}: {result.returncode}", flush=True)
    if (result.returncode == 0) != success:
        raise AssertionError(result.stdout + result.stderr)
    return result


def check(stage):
    Path("/work/tmp").mkdir()
    for key in os.environ:
        assert not key.startswith(("PIXI_", "CONDA_", "MOJO_BINDGEN_")), key
    tools = {name: shutil.which(name) for name in ("cc", "gcc", "clang", "ld")}
    has_headers = Path("/usr/include/stdio.h").is_file()
    metadata = importlib.metadata.metadata("mojo-bindgen")
    assert metadata["Requires-Python"] == ">=3.14"
    assert sys.version_info >= (3, 14)
    for library in ("libstdc++.so.6", "libgcc_s.so.1"):
        ctypes.CDLL(library)
    packages = run(
        ["dpkg-query", "-W", "-f=${Package}=${Version}\n", "libc6", "libgcc-s1", "libstdc++6"]
    )
    print(
        json.dumps(
            {
                "stage": stage,
                "os": Path("/etc/os-release").read_text(),
                "python": sys.version,
                "libc": platform.libc_ver(),
                "tools": tools,
                "stdio_header": has_headers,
                "system_runtimes": packages.stdout.splitlines(),
                "requires_python": metadata["Requires-Python"],
            },
            indent=2,
        ),
        flush=True,
    )
    assert tools["clang"] is None
    if stage == "installed":
        assert not has_headers
        assert not any(tools.values()), tools
    elif stage == "headers":
        assert has_headers and not tools["cc"] and not tools["gcc"] and not tools["ld"], tools
    else:
        assert has_headers and tools["cc"] and tools["ld"], tools

    # The installer must enforce interpreter requirements, independently of deps.
    rejected = run(
        [
            sys.executable,
            "-m",
            "pip",
            "--isolated",
            "install",
            "--dry-run",
            "--no-deps",
            "--no-index",
            "--python-version",
            "3.13",
            str(next(Path("/wheel").glob("*.whl"))),
        ],
        success=False,
    )
    assert "requires a different Python" in rejected.stderr, rejected.stderr

    command = shutil.which("mojo-bindgen")
    assert command
    assert run([command, "--version"]).stdout.strip() == "mojo-bindgen 0.4.0"
    assert "--link-mode" in run([command, "--help"]).stdout
    assert (
        "complete" in run(["/bin/bash", "-c", 'mojo-bindgen --show-completion; exit "$?"']).stdout
    )
    library = Path(run([command, "--print-mojo-path"]).stdout.strip())
    direct = library.parent / "bin/mojo-bindgen"
    shutil.copy2("/probe/native_smoke.h", ".")
    header = Path("native_smoke.h")
    for mode in ("external-call", "owned-dl-handle"):
        args = [
            str(header),
            f"--link-mode={mode}",
            "--dump-cir=cir.json",
            "--dump-mojo-ir=mojo.json",
            "--layout-tests=layout.mojo",
            "--diagnostics=silent",
        ]
        facade_result = run([command, *args])
        raw_result = run([str(direct), *args])
        assert not facade_result.stderr, facade_result.stderr
        assert not raw_result.stderr, raw_result.stderr
        facade = facade_result.stdout
        raw = raw_result.stdout
        assert facade == raw and "native_accept" in raw and "NativeNode" in raw
        assert "\x1b" not in facade
        assert json.loads(Path("cir.json").read_text())["kind"] == "Unit"
        assert json.loads(Path("mojo.json").read_text())["kind"] == "MojoModule"
        assert "def main() raises:" in Path("layout.mojo").read_text()

    # Clang builtin headers are packaged, even without a system libc development package.
    Path("builtin.h").write_text(
        "#include <stdint.h>\n#include <stddef.h>\nstruct Builtin { uint64_t value; size_t size; };\n"
    )
    assert "Builtin" in run([command, "builtin.h"]).stdout
    Path("system.h").write_text("#include <stdio.h>\nint accepts_file(FILE *file);\n")
    stdio = run([command, "system.h"], success=has_headers)
    if has_headers:
        assert "accepts_file" in stdio.stdout
    else:
        assert "stdio.h" in stdio.stderr and "not found" in stdio.stderr, stdio.stderr

    preprocess = run([command, str(header), "--dump-preprocessed=output.h"], success=False)
    assert "clang" in preprocess.stderr, preprocess.stderr
    assert "No such file" in preprocess.stderr or "not found" in preprocess.stderr, (
        preprocess.stderr
    )

    # Compile a consumer only after explicitly supplying a system linker/toolchain.
    clang = library.parents[2] / "clang/native/libclang.so"
    assert clang.is_file(), clang
    env = {
        **os.environ,
        "MOJO_BINDGEN_CLANG_LIBRARY_PATH": str(clang),
        "MOJO_BINDGEN_CLANG_RESOURCE_DIR": str(library.parent / "lib/clang/18"),
    }
    api = run(
        [
            "mojo",
            "build",
            "--Werror",
            "-I",
            str(library),
            "/probe/test_import.mojo",
            "-o",
            "/work/api-test",
        ],
        success=stage == "toolchain",
        env=env,
    )
    if stage == "toolchain":
        run(["/work/api-test"], env=env)
    else:
        assert "link" in api.stderr.lower() or "compiler" in api.stderr.lower(), api.stderr
    print(
        "MINIMAL_OS_RESULT="
        + json.dumps(
            {
                "stage": stage,
                "python": platform.python_version(),
                "libc": platform.libc_ver(),
                "system_runtimes": packages.stdout.splitlines(),
                "tools": tools,
                "stdio_header": has_headers,
                "requires_python": metadata["Requires-Python"],
                "python_313_rejected": True,
                "binding_modes": ["external-call", "owned-dl-handle"],
                "public_api_compiled": stage == "toolchain",
                "pip_install": json.loads(Path("/installation.json").read_text()),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("installed", "headers", "toolchain"))
    check(parser.parse_args().stage)

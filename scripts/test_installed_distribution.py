"""Exercise the installed wheel, public Mojo executable/API and stable FFI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path

from native_testing.build import build_target

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "mojo/.pixi/envs/default"
STABLE = ROOT / "mojo/.pixi/envs/stable-tests"


def run(command, *, cwd, env):
    result = subprocess.run(
        list(map(str, command)), cwd=cwd, env=env, text=True, capture_output=True, timeout=300
    )
    if result.returncode:
        raise RuntimeError(f"failed: {command}\n{result.stdout}{result.stderr}")
    return result


def clean_environment():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("PIXI_", "CONDA_", "MODULAR_", "MOJO_BINDGEN_")) or key in (
            "PYTHONPATH",
            "LD_LIBRARY_PATH",
            "CPATH",
            "CC",
            "CXX",
            "LD",
            "CFLAGS",
            "CXXFLAGS",
            "LDFLAGS",
            "LIBRARY_PATH",
        ):
            env.pop(key, None)
    env.update(PATH="/usr/bin:/bin", NO_COLOR="1")
    return env


def compiler_environment(prefix):
    env = clean_environment()
    env.update(
        CONDA_PREFIX=str(prefix),
        MODULAR_HOME=str(prefix / "share/max"),
        LD_LIBRARY_PATH=str(prefix / "lib"),
    )
    env["PATH"] = str(prefix / "bin") + os.pathsep + env["PATH"]
    return env


def check(wheel):
    if wheel.stat().st_size > 10_000_000:
        raise ValueError(f"wheel exceeds the release size budget: {wheel.stat().st_size}")
    parent = ROOT / "mojo/build/installed-tests"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="installed λ ", dir=parent) as temporary:
        work = Path(temporary)
        environment = work / "environment"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / "bin/python"
        env = clean_environment()
        run(
            [
                python,
                "-m",
                "pip",
                "--isolated",
                "--disable-pip-version-check",
                "install",
                "--no-cache-dir",
                "--extra-index-url",
                "https://whl.modular.com/nightly/simple/",
                wheel,
            ],
            cwd=work,
            env=env,
        )
        facade = environment / "bin/mojo-bindgen"
        version = run([facade, "--version"], cwd=work, env=env).stdout.strip()
        assert version == "mojo-bindgen 0.4.0", version
        assert "--link-mode" in run([facade, "--help"], cwd=work, env=env).stdout
        assert "complete" in run([facade, "--show-completion", "bash"], cwd=work, env=env).stdout
        directory = Path(run([facade, "--print-mojo-path"], cwd=work, env=env).stdout.strip())
        payload = directory.parent
        command = payload / "bin/mojo-bindgen"
        assert run([command, "--version"], cwd=work, env=env).stdout.strip() == version
        probe = run(
            [
                python,
                "-I",
                "-c",
                "import mojo_bindgen,importlib.util; assert not hasattr(mojo_bindgen,'bindgen'); assert importlib.util.find_spec('mojo_bindgen.parsing') is None; print(mojo_bindgen.__file__)",
            ],
            cwd=work,
            env=env,
        ).stdout
        assert str(environment) in probe, probe
        # Relocation must preserve direct execution and its public library location.
        site = Path(
            run(
                [python, "-I", "-c", "import sysconfig; print(sysconfig.get_path('platlib'))"],
                cwd=work,
                env=env,
            ).stdout.strip()
        )
        clang = site / "clang/native/libclang.so"
        assert clang.is_file()
        relocated_site = work / "relocated installation/site-packages"
        relocated = relocated_site / "mojo_bindgen/payload"
        shutil.copytree(payload, relocated)
        for name in (
            "libKGENCompilerRTShared.so",
            "libMSupportGlobals.so",
            "libAsyncRTRuntimeGlobals.so",
        ):
            target = relocated_site / "modular/lib" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(site / "modular/lib" / name, target)
        (relocated_site / "clang/native").mkdir(parents=True)
        shutil.copy2(clang, relocated_site / "clang/native/libclang.so")
        assert (
            run([relocated / "bin/mojo-bindgen", "--version"], cwd=work, env=env).stdout.strip()
            == version
        )

        count = 0
        reference = build_target("cli", 3)
        reference_env = compiler_environment(SDK)
        reference_env["MOJO_BINDGEN_CLANG_LIBRARY_PATH"] = str(SDK / "lib/libclang.so")
        reference_env["MOJO_BINDGEN_CLANG_RESOURCE_DIR"] = str(payload / "lib/clang/18")
        roots = (
            "corpus/headers",
            "surface/fixtures",
            "stress/fixtures",
            "e2e/fixtures",
            "surface/alignment/fixtures",
        )
        for subtree in roots:
            for source in sorted((ROOT / "tests" / subtree).glob("*/input.h")):
                target = work / "headers" / source.relative_to(ROOT / "tests")
                target.parent.mkdir(parents=True, exist_ok=True)
                for header in source.parent.rglob("*.h"):
                    destination = target.parent / header.relative_to(source.parent)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(header, destination)
                for mode in ("external-call", "owned-dl-handle"):
                    arguments = [
                        target,
                        "--library=testlib",
                        "--link-name=testlib",
                        f"--link-mode={mode}",
                        "--diagnostics=silent",
                    ]
                    direct = run([command, *arguments], cwd=work, env=env)
                    presented = run([facade, *arguments], cwd=work, env=env)
                    assert direct.stdout == presented.stdout, str(source)
                    assert "\x1b" not in presented.stdout
                    expected = run([reference, *arguments], cwd=work, env=reference_env)
                    assert direct.stdout == expected.stdout, f"libclang provider: {source} {mode}"
                    layout = work / "layout.mojo"
                    layout_args = [*arguments, "--layout-tests", layout]
                    run([command, *layout_args], cwd=work, env=env)
                    actual_layout = layout.read_bytes()
                    run([reference, *layout_args], cwd=work, env=reference_env)
                    assert actual_layout == layout.read_bytes(), f"provider layout: {source} {mode}"
                    count += 1
        assert count >= 98, count
        run([relocated / "bin/mojo-bindgen", target], cwd=work, env=env)

        # Some Linux systems select Clang, rather than GCC, through cc.
        clang_driver = shutil.which("clang", path=env["PATH"])
        if clang_driver is None:
            raise RuntimeError("system Clang is required for installed preprocessing checks")
        drivers = work / "clang-as-cc"
        drivers.mkdir()
        (drivers / "cc").symlink_to(clang_driver)
        clang_env = {**env, "PATH": str(drivers) + os.pathsep + env["PATH"]}
        atomic = work / "headers/corpus/headers/atomic_scalar_and_field/input.h"
        for mode in ("external-call", "owned-dl-handle"):
            assert (
                "asf_state"
                in run(
                    [command, atomic, f"--link-mode={mode}", "--diagnostics=silent"],
                    cwd=work,
                    env=clang_env,
                ).stdout
            )

        # Exercise system preprocessing, diagnostic JSON and both debug dump paths.
        header = work / "native_smoke.h"
        shutil.copy2(ROOT / "mojo/conda.recipe/native_smoke.h", header)
        arguments = [
            header,
            "-o",
            work / "smoke.mojo",
            "--dump-cir",
            work / "cir.json",
            "--dump-mojo-ir",
            work / "module.json",
            "--dump-preprocessed",
            work / "preprocessed.h",
            "--diagnostics=json",
            "--diagnostics-output",
            work / "diagnostics.json",
        ]
        run([facade, *arguments], cwd=work, env=env)
        assert json.loads((work / "cir.json").read_text())["kind"] == "Unit"
        assert json.loads((work / "module.json").read_text())["kind"] == "MojoModule"
        assert (work / "preprocessed.h").stat().st_size > 0
        assert json.loads((work / "diagnostics.json").read_text())[0]["severity"] == "warning"

        # Call the public Mojo API through installed compiled modules only.
        api_env = clean_environment()
        api_env["PATH"] = str(environment / "bin") + os.pathsep + api_env["PATH"]
        api_env["MOJO_BINDGEN_CLANG_LIBRARY_PATH"] = str(clang)
        api_env["MOJO_BINDGEN_CLANG_RESOURCE_DIR"] = str(payload / "lib/clang/18")
        run(
            [
                environment / "bin/mojo",
                "build",
                "--Werror",
                "-I",
                directory,
                ROOT / "mojo/conda.recipe/test_import.mojo",
                "-o",
                work / "api-test",
            ],
            cwd=work,
            env=api_env,
        )
        run([work / "api-test"], cwd=work, env=api_env)

        # Inherited stable runtime paths must not select the generator's runtime.
        stable = compiler_environment(STABLE)
        run([command, header, "--diagnostics=silent"], cwd=work, env=stable)
        run([facade, header, "--diagnostics=silent"], cwd=work, env=stable)
        runtime_header = work / "runtime.h"
        runtime_header.write_text(
            "struct Node { int value; int other; };\nint installed_add(int a,int b);\n"
        )
        (work / "impl.c").write_text("int installed_add(int a,int b) { return a+b; }\n")
        run(
            ["cc", "-shared", "-fPIC", work / "impl.c", "-o", work / "libinstalled.so"],
            cwd=work,
            env=env,
        )
        (work / "runner.mojo").write_text(
            "from std.testing import assert_equal\nfrom bindings import installed_add\n\ndef main() raises:\n    assert_equal(installed_add(2,3),5)\n"
        )
        for mode in ("external-call", "owned-dl-handle"):
            run(
                [
                    facade,
                    runtime_header,
                    "--library=installed",
                    "--link-name=installed",
                    f"--link-mode={mode}",
                    f"--library-path={work / 'libinstalled.so'}",
                    "-o",
                    work / "bindings.mojo",
                    "--layout-tests",
                    work / "layout.mojo",
                ],
                cwd=work,
                env=env,
            )
            for source in ("runner.mojo", "layout.mojo"):
                executable = work / source.removesuffix(".mojo")
                run(
                    [
                        STABLE / "bin/mojo",
                        "build",
                        "--Werror",
                        "-D",
                        "ASSERT=all",
                        "-I",
                        work,
                        "-Xlinker",
                        f"-L{work}",
                        "-Xlinker",
                        "-linstalled",
                        work / source,
                        "-o",
                        executable,
                    ],
                    cwd=work,
                    env=stable,
                )
                runtime_env = {
                    **stable,
                    "LD_LIBRARY_PATH": str(work) + os.pathsep + stable["LD_LIBRARY_PATH"],
                }
                run([executable], cwd=work, env=runtime_env)
        print(
            f"Installed wheel passed: {count} header/mode comparisons across facade/direct and PyPI/Conda libclang providers, identical layouts, relocated executable, public Mojo API, debug/preprocessing/diagnostics, and both stable FFI/layout modes"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    check(parser.parse_args().wheel.resolve())

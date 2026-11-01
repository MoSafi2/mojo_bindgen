"""Resolve the release channel in a fresh consumer and check installed interfaces."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import tomllib
from pathlib import Path

from test_installed_distribution import ROOT, clean_environment, compiler_environment, run


def check(channel):
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    pixi = shutil.which("pixi")
    if pixi is None:
        raise RuntimeError("Pixi is required for the installed channel acceptance check")
    parent = ROOT / "mojo/build/installed-tests"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="conda-consumer-", dir=parent) as directory:
        work = Path(directory)
        manifest = work / "pixi.toml"
        channels = [
            channel.resolve().as_uri(),
            "https://conda.modular.com/max-nightly/",
            "conda-forge",
        ]
        manifest.write_text(
            '[workspace]\nname = "bindgen-consumer"\nplatforms = ["linux-64"]\n'
            + f"channels = {json.dumps(channels)}\n\n"
            + '[system-requirements]\nlibc = { family = "glibc", version = "2.35" }\n\n[dependencies]\n'
            + f'mojo-bindgen = "=={version}"\n'
        )
        env = clean_environment()
        run([pixi, "install", "--manifest-path", manifest], cwd=work, env=env)
        prefix = work / ".pixi/envs/default"
        env = compiler_environment(prefix)
        facade = prefix / "bin/mojo-bindgen"
        assert (
            run([facade, "--version"], cwd=work, env=env).stdout.strip()
            == f"mojo-bindgen {version}"
        )
        library = Path(run([facade, "--print-mojo-path"], cwd=work, env=env).stdout.strip())
        command = library.parent / "bin/mojo-bindgen"
        shutil.copy2(ROOT / "mojo/conda.recipe/native_smoke.h", work)
        for executable in (facade, command):
            run([executable, "native_smoke.h", "-o", work / "bindings.mojo"], cwd=work, env=env)
        run(
            [
                prefix / "bin/mojo",
                "build",
                "--Werror",
                ROOT / "mojo/conda.recipe/test_import.mojo",
                "-o",
                work / "api",
            ],
            cwd=work,
            env=env,
        )
        run([work / "api"], cwd=work, env=env)
        metadata = next(
            (prefix / "lib").glob("python*/site-packages/mojo_bindgen-*.dist-info/METADATA")
        ).read_text()
        assert "Requires-Dist: libclang" not in metadata
        assert "Requires-Dist: mojo-compiler" not in metadata
    print(
        "Fresh release-channel installation passed: facade, direct executable, public Mojo API and Conda dependency mapping"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("channel", type=Path)
    check(parser.parse_args().channel)

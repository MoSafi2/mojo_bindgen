"""Assemble the compiled Mojo distribution when building a platform wheel."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name != "wheel" or version == "editable":
            return
        root = Path(self.root)
        if not os.environ.get("MOJO_BINDGEN_CONDA"):
            runtime = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["mojo-bindgen"][
                "runtime-dependencies"
            ]
            build_data["dependencies"].extend(
                name + constraint for name, constraint in runtime.items()
            )
        output = Path(os.environ.get("MOJO_BINDGEN_PAYLOAD", root / "mojo/build/payload"))
        subprocess.run(
            [
                sys.executable,
                str(root / "scripts/prepare_distribution.py"),
                "--output",
                str(output),
            ],
            check=True,
        )
        build_data["pure_python"] = False
        floor = json.loads((output / "manifest.json").read_text())["glibc"].replace(".", "_")
        build_data["tag"] = f"py3-none-manylinux_{floor}_x86_64"
        build_data["force_include"][str(output)] = "mojo_bindgen/payload"

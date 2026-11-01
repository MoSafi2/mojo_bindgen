"""Check the identity shared by the CLI, Mojo library and distribution recipes."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(tag=None, revision=None):
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    manifest = tomllib.loads((ROOT / "mojo/pixi.toml").read_text())
    version = project["project"]["version"]
    native = manifest["workspace"]["version"]
    pin = project["tool"]["mojo-bindgen"]["runtime-dependencies"]["mojo-compiler"]
    if pin != manifest["dependencies"]["mojo"]:
        raise ValueError("wheel and development compiler pins differ")
    python = next(
        ast.literal_eval(node.value)
        for node in ast.parse((ROOT / "mojo_bindgen/__init__.py").read_text()).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
    )
    mojo = re.search(
        r'comptime VERSION = "([^"]+)"', (ROOT / "mojo/mojo_bindgen/_version.mojo").read_text()
    ).group(1)
    recipe = re.search(
        r'^  version: "([^"]+)"', (ROOT / "mojo/conda.recipe/recipe.yaml").read_text(), re.M
    ).group(1)
    identities = {
        "project": version,
        "Mojo manifest": native,
        "Python facade": python,
        "Mojo API": mojo,
        "Conda": recipe,
    }
    if set(identities.values()) != {version}:
        raise ValueError(f"inconsistent release identities: {identities}")
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"tag {tag} does not match v{version}")
    if revision is not None:
        if not re.fullmatch(r"[a-f0-9]{40}", revision):
            raise ValueError("release source revision must be a complete immutable commit SHA")
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        if actual != revision:
            raise ValueError(f"source revision mismatch: {actual} != {revision}")
    print(f"Validated mojo-bindgen {version}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    parser.add_argument("--revision")
    arguments = parser.parse_args()
    check(arguments.tag, arguments.revision)

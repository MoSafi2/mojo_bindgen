"""Render a release recipe pinned to an immutable source revision."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(revision: str, destination: Path) -> Path:
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("release recipes require a complete commit SHA")
    source = ROOT / "mojo/conda.recipe"
    destination.mkdir(parents=True, exist_ok=True)
    text = (source / "recipe.yaml").read_text()
    old = "source:\n  path: ../.."
    if text.count(old) != 1:
        raise ValueError("unexpected development source declaration")
    text = text.replace(
        old, f"source:\n  git: https://github.com/MoSafi2/mojo_bindgen.git\n  rev: {revision}"
    )
    (destination / "recipe.yaml").write_text(text)
    for name in ("test_import.mojo", "native_smoke.h"):
        shutil.copy2(source / name, destination / name)
    return destination / "recipe.yaml"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(render(args.revision, args.destination))

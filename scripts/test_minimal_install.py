"""Test the wheel on a pinned minimal OS, without any host SDK or checkout mounts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_IMAGE = "python@sha256:516b51cb9db2ef061e465c803e50f64361b82cefd91e525b889b967b83e83527"
STAGES = ("installed", "headers", "toolchain")


def command(arguments, log, *, timeout=600):
    with log.open("w") as stream:
        result = subprocess.run(arguments, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}); see {log}\n{log.read_text()[-12000:]}"
        )
    return log.read_text()


def check(wheel, output, image):
    if not shutil.which("docker"):
        raise RuntimeError("Docker is required for the minimal-OS installation gate")
    output.mkdir(parents=True, exist_ok=True)
    run_id = str(time.time_ns())
    images = []
    results = []
    report = {
        "base_image": image,
        "platform": "linux/amd64",
        "wheel": wheel.name,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "results": results,
    }
    try:
        command(["docker", "pull", "--platform", "linux/amd64", image], output / "pull.log")
        with tempfile.TemporaryDirectory(prefix="context-", dir=output) as directory:
            context = Path(directory)
            (context / "wheel").mkdir()
            shutil.copy2(wheel, context / "wheel" / wheel.name)
            fixtures = ROOT / "tests/distribution/minimal_os"
            for name in ("Dockerfile", "probe.py"):
                shutil.copy2(fixtures / name, context / name)
            for name in ("native_smoke.h", "test_import.mojo"):
                shutil.copy2(ROOT / "mojo/conda.recipe" / name, context / name)
            for stage in STAGES:
                tag = f"mojo-bindgen-minimal-test:{run_id}-{stage}"
                images.append(tag)
                print(f"Build and probe minimal OS: {stage}", flush=True)
                command(
                    [
                        "docker",
                        "build",
                        "--platform",
                        "linux/amd64",
                        "--build-arg",
                        f"BASE_IMAGE={image}",
                        "--target",
                        stage,
                        "--tag",
                        tag,
                        str(context),
                    ],
                    output / f"{stage}-build.log",
                )
                text = command(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--platform",
                        "linux/amd64",
                        "--network",
                        "none",
                        "--cap-drop",
                        "ALL",
                        "--security-opt",
                        "no-new-privileges",
                        "--read-only",
                        "--user",
                        "65532:65532",
                        "--tmpfs",
                        "/work:rw,exec,nosuid,nodev,mode=1777,size=1g",
                        "--tmpfs",
                        "/tmp:rw,exec,nosuid,nodev,mode=1777,size=256m",
                        "--env",
                        "HOME=/work",
                        "--env",
                        "TMPDIR=/work/tmp",
                        tag,
                        "python",
                        "/probe/probe.py",
                        stage,
                    ],
                    output / f"{stage}-probe.log",
                )
                marker = "MINIMAL_OS_RESULT="
                data = [
                    json.loads(line[len(marker) :])
                    for line in text.splitlines()
                    if line.startswith(marker)
                ]
                if len(data) != 1 or data[0]["stage"] != stage:
                    raise RuntimeError(f"missing/incomplete container report: {stage}")
                results.append(data[0])
                print(f"PASS minimal OS: {stage}", flush=True)
    finally:
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        for tag in reversed(images):
            subprocess.run(["docker", "image", "rm", tag], capture_output=True, timeout=60)
    assert len(results) == len(STAGES)
    print(f"Minimal OS installation passed in all {len(STAGES)} stages; {output / 'report.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--image", default=BASE_IMAGE)
    parser.add_argument("--output", type=Path, default=ROOT / "mojo/build/minimal-os")
    args = parser.parse_args()
    check(args.wheel.resolve(), args.output.resolve(), args.image)

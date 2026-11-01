"""Build a relocatable Linux payload shared by the wheel and Conda distribution."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path

from compression import zstd

ROOT = Path(__file__).resolve().parents[1]
MOJO_VERSION = "1.3.0.dev2026103105"


def run(command, **kwargs):
    return subprocess.run(list(map(str, command)), check=True, text=True, **kwargs)


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sdk_environment(prefix, scratch):
    env = os.environ.copy()
    for name in ("CC", "CXX", "LD", "CFLAGS", "CXXFLAGS", "LDFLAGS", "LIBRARY_PATH"):
        env.pop(name, None)
    env.update(
        {
            "CONDA_PREFIX": str(prefix),
            "MODULAR_HOME": str(prefix / "share/max"),
            "LD_LIBRARY_PATH": str(prefix / "lib"),
            "PATH": str(prefix / "bin") + os.pathsep + "/usr/bin:/bin",
            "TMPDIR": str(scratch),
        }
    )
    return env


def source_identity(prefix):
    sources = [ROOT / "pyproject.toml", ROOT / "LICENSE", ROOT / "mojo/main.mojo", Path(__file__)]
    sources += sorted((ROOT / "mojo/mojo_bindgen").rglob("*.mojo"))
    sources += sorted((prefix / "conda-meta").glob("*.json"))
    digest = hashlib.sha256()
    for path in sources:
        digest.update(
            str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name).encode()
        )
        digest.update(path.read_bytes())
    return digest.hexdigest()


def download_notices(package, destination):
    """Environment caches need not retain Conda's separate package-info cache."""
    expected = package.get("sha256")
    if not expected:
        raise RuntimeError(f"missing immutable artifact checksum for {package['name']}")
    with urllib.request.urlopen(package["url"], timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"dependency artifact checksum mismatch: {package['name']}")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = next(name for name in archive.namelist() if name.startswith("info-"))
        payload = zstd.decompress(archive.read(info))
    found = False
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.startswith("info/licenses/"):
                continue
            relative = Path(member.name).relative_to("info/licenses")
            if ".." in relative.parts:
                raise RuntimeError("invalid dependency notice path")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError("missing dependency notice")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            found = True
    if not found:
        raise RuntimeError(f"dependency artifact has no redistribution notices: {package['name']}")


def copy_notices(stage, sdk):
    owners = {"mojo-compiler", "libclang_mojo", "clang-18"}
    found = set()
    for record in sorted((sdk / "conda-meta").glob("*.json")):
        package = json.loads(record.read_text())
        name = package["name"]
        if name not in owners:
            continue
        extracted = Path(package.get("extracted_package_dir") or package["link"]["source"])
        licenses = extracted / "info/licenses"
        destination = stage / "licenses" / name
        if licenses.is_dir():
            shutil.copytree(licenses, destination, dirs_exist_ok=True)
        else:
            installed = [
                sdk / f for f in package.get("files", []) if f.startswith("share/licenses/")
            ]
            if installed:
                destination.mkdir(parents=True)
                for source in installed:
                    shutil.copy2(source, destination / source.name)
            else:
                download_notices(package, destination)
        (destination / "package.json").write_text(
            json.dumps(
                {
                    key: package.get(key)
                    for key in ("name", "version", "build", "license", "url", "sha256")
                },
                indent=2,
            )
            + "\n"
        )
        found.add(name)
    if not owners.issubset(found):
        raise RuntimeError(f"missing dependency license records: {owners - found}")
    shutil.copy2(ROOT / "LICENSE", stage / "licenses/mojo-bindgen-LICENSE")


def validate_elf(stage):
    for path in [*(stage / "bin").iterdir(), *(stage / "lib").glob("*.so*")]:
        if not path.is_file() or path.read_bytes()[:4] != b"\x7fELF":
            continue
        dynamic = run(["readelf", "-d", path], capture_output=True).stdout
        for line in dynamic.splitlines():
            if "RPATH" in line or "RUNPATH" in line:
                if str(ROOT) in line or "/.pixi/" in line or "_h_env" in line:
                    raise RuntimeError(f"build-prefix RPATH in {path}: {line}")
        versions = run(["readelf", "--version-info", path], capture_output=True).stdout
        required = [tuple(map(int, pair)) for pair in re.findall(r"\bGLIBC_(\d+)\.(\d+)", versions)]
        if required and max(required) > (2, 35):
            raise RuntimeError(
                f"{path.name} exceeds the declared glibc 2.35 floor: {max(required)}"
            )


def prepare(output, sdk, patchelf):
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    compiler = sdk / "bin/mojo"
    if not compiler.is_file():
        raise RuntimeError(
            f"missing pinned Mojo SDK: {sdk}. Install mojo/pixi.toml or set MOJO_BINDGEN_SDK."
        )
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("release payloads currently support Linux x86-64")
    identity = source_identity(sdk)
    manifest = output / "manifest.json"
    if manifest.is_file():
        previous = json.loads(manifest.read_text())
        if previous.get("source_identity") == identity and all(
            (output / name).is_file() and checksum(output / name) == digest
            for name, digest in previous["files"].items()
        ):
            print(f"Reusing verified mojo-bindgen {version} payload: {output}")
            return
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="payload-", dir=output.parent) as directory:
        stage = Path(directory)
        for name in ("bin", "lib", "mojo", "licenses", "tmp"):
            (stage / name).mkdir()
        env = sdk_environment(sdk, stage / "tmp")
        probe = run([compiler, "--version"], env=env, capture_output=True).stdout
        if f"Mojo {MOJO_VERSION} " not in probe:
            raise RuntimeError(f"wrong compiler: expected {MOJO_VERSION}, got {probe}")
        run(
            [
                compiler,
                "precompile",
                "--Werror",
                "-I",
                sdk / "lib/mojo",
                ROOT / "mojo/mojo_bindgen",
                "-o",
                stage / "mojo/mojo_bindgen.mojoc",
            ],
            env=env,
        )
        run(
            [
                compiler,
                "build",
                "--Werror",
                "-O3",
                "--target-cpu",
                "x86-64-v3",
                "--num-threads",
                "1",
                "-I",
                ROOT / "mojo",
                ROOT / "mojo/main.mojo",
                "-o",
                stage / "bin/mojo-bindgen",
            ],
            env=env,
        )
        shutil.copy2(sdk / "lib/mojo/clang.mojoc", stage / "mojo/clang.mojoc")
        resource = Path(
            run(
                [sdk / "bin/clang", "-print-resource-dir"], env=env, capture_output=True
            ).stdout.strip()
        )
        if not resource.is_relative_to(sdk):
            raise RuntimeError(f"unexpected Clang resource directory: {resource}")
        shutil.copytree(
            resource / "include",
            stage / "lib/clang" / resource.name / "include",
            ignore=lambda directory, names: [
                name
                for name in names
                if (Path(directory) / name).is_symlink() and not (Path(directory) / name).exists()
            ],
        )
        copy_notices(stage, sdk)
        command = stage / "bin/mojo-bindgen"
        run(["strip", "--strip-unneeded", command])
        # Wheels share Modular's runtime; Conda supplies it in the environment's lib.
        run(
            [
                patchelf,
                "--force-rpath",
                "--set-rpath",
                "$ORIGIN/../../../modular/lib:$ORIGIN/../../../../..",
                command,
            ]
        )
        validate_elf(stage)
        shutil.rmtree(stage / "tmp")
        files = {
            str(p.relative_to(stage)): checksum(p) for p in sorted(stage.rglob("*")) if p.is_file()
        }
        (stage / "manifest.json").write_text(
            json.dumps(
                {
                    "version": version,
                    "mojo_version": MOJO_VERSION,
                    "target_cpu": "x86-64-v3",
                    "glibc": "2.35",
                    "source_identity": identity,
                    "files": files,
                },
                indent=2,
            )
            + "\n"
        )
        if output.exists():
            shutil.rmtree(output)
        shutil.move(stage, output)
    print(f"Built mojo-bindgen {version} payload: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sdk-prefix",
        type=Path,
        default=Path(os.environ.get("MOJO_BINDGEN_SDK", ROOT / "mojo/.pixi/envs/default")),
    )
    parser.add_argument("--output", type=Path, default=ROOT / "mojo/build/payload")
    parser.add_argument(
        "--patchelf",
        default=os.environ.get("MOJO_BINDGEN_PATCHELF")
        or shutil.which("patchelf")
        or str(ROOT / "mojo/.pixi/envs/package/bin/patchelf"),
    )
    args = parser.parse_args()
    prepare(args.output.resolve(), args.sdk_prefix.resolve(), args.patchelf)


if __name__ == "__main__":
    main()

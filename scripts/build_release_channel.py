"""Create the checksum-pinned GitHub release's local Conda channel archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from compression import zstd

ROOT = Path(__file__).resolve().parents[1]


def digest(path, algorithm="sha256"):
    value = hashlib.new(algorithm)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def index(path):
    with zipfile.ZipFile(path) as package:
        info = next(name for name in package.namelist() if name.startswith("info-"))
        with tarfile.open(fileobj=io.BytesIO(zstd.decompress(package.read(info)))) as archive:
            metadata = archive.extractfile("info/index.json")
            if metadata is None:
                raise ValueError(f"missing package index: {path}")
            result = json.load(metadata)
    result.update(sha256=digest(path), md5=digest(path, "md5"), size=path.stat().st_size)
    return result


def build(output):
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    packages = list((ROOT / "mojo/build/conda/linux-64").glob(f"mojo-bindgen-{version}-*.conda"))
    dependency = tomllib.loads((ROOT / "mojo/pixi.toml").read_text())["dependencies"][
        "libclang_mojo"
    ]
    upstream = list(
        (ROOT / "mojo/build/upstream-channel").rglob(Path(urlparse(dependency["url"]).path).name)
    )
    if len(packages) != 1 or len(upstream) != 1:
        raise ValueError(
            f"expected one current bindgen and one pinned upstream package: {packages}, {upstream}"
        )
    if digest(upstream[0]) != dependency["sha256"]:
        raise ValueError("upstream package does not match the pinned dependency checksum")
    output.mkdir(parents=True, exist_ok=True)
    channel = output / f"mojo-bindgen-{version}-channel"
    if channel.exists():
        shutil.rmtree(channel)
    for subdir in ("linux-64", "noarch"):
        (channel / subdir).mkdir(parents=True)
        records = {}
        for package in [*packages, *upstream] if subdir == "linux-64" else []:
            shutil.copy2(package, channel / subdir / package.name)
            records[package.name] = index(package)
        (channel / subdir / "repodata.json").write_text(
            json.dumps(
                {
                    "info": {"subdir": subdir},
                    "packages": {},
                    "packages.conda": records,
                    "repodata_version": 2,
                },
                indent=2,
            )
            + "\n"
        )
    (channel / "channeldata.json").write_text(
        json.dumps(
            {
                "channeldata_version": 1,
                "subdirs": ["linux-64", "noarch"],
                "packages": {},
            }
        )
        + "\n"
    )
    archive_path = output / f"{channel.name}.tar.gz"
    with (
        archive_path.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed,
    ):
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for path in [channel, *sorted(channel.rglob("*"))]:
                info = archive.gettarinfo(str(path), str(path.relative_to(output)))
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                with path.open("rb") if path.is_file() else io.BytesIO() as data:
                    archive.addfile(info, data if path.is_file() else None)
    shutil.copy2(packages[0], output / packages[0].name)
    artifacts = sorted(p for p in output.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (output / "SHA256SUMS").write_text("".join(f"{digest(p)}  {p.name}\n" for p in artifacts))
    print(archive_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/release")
    build(parser.parse_args().output)

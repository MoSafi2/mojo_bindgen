"""Prepare the checksum-pinned upstream release channel for native package builds."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request

ARCHIVE = "libclang_mojo-0.3.0.dev20261031-conda-channel.tar.gz"
URL = f"https://github.com/MoSafi2/mojo_libclang/releases/download/v0.3.0-dev.20261031/{ARCHIVE}"
SHA256 = "4fc36b8f450c8286792699c1d2090d52645c12f115d2145983e8003d3b539d19"


def main() -> None:
    directory = Path(__file__).resolve().parents[1] / "mojo/build/upstream-channel"
    marker = directory / ".sha256"
    if not marker.exists() or marker.read_text() != SHA256:
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError("mojo_libclang release channel checksum mismatch")
        directory.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            archive.extractall(directory, filter="data")
        marker.write_text(SHA256)
    channels = sorted(path.parent for path in directory.rglob("channeldata.json"))
    if not channels:
        channels = sorted({path.parent.parent for path in directory.rglob("repodata.json")})
    if len(channels) != 1:
        raise ValueError(f"expected one upstream channel, found {len(channels)}")
    print(channels[0].as_uri())


if __name__ == "__main__":
    main()

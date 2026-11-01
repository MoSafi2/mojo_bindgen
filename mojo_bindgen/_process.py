"""Locate this installation's Mojo command and supervise its process group."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def executable() -> Path:
    override = os.environ.get("MOJO_BINDGEN_EXECUTABLE")
    path = Path(override) if override else Path(__file__).parent / "payload/bin/mojo-bindgen"
    if not path.is_file():
        raise FileNotFoundError(
            f"mojo-bindgen: packaged Mojo executable is missing: {path}. "
            "Reinstall the platform wheel or Conda package. "
            "For checkout development, run pixi run native-build."
        )
    return path.resolve()


def mojo_path() -> Path:
    path = executable().parent.parent / "mojo"
    if not (path / "mojo_bindgen.mojoc").is_file():
        raise FileNotFoundError(f"mojo-bindgen: installed Mojo library is missing: {path}")
    return path


def invoke(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    command = [str(executable()), *arguments]
    env = os.environ.copy()
    sdk = env.get("MOJO_BINDGEN_SDK")
    if env.get("MOJO_BINDGEN_EXECUTABLE") and sdk and (Path(sdk) / "lib").is_dir():
        env["LD_LIBRARY_PATH"] = str(Path(sdk) / "lib")
        env.setdefault("MOJO_BINDGEN_CLANG_LIBRARY_PATH", str(Path(sdk) / "lib/libclang.so"))
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        start_new_session=True,
        env=env,
    )
    try:
        stdout, stderr = process.communicate()
    except BaseException:
        # The command may have launched clang; interrupt the entire group and reap it.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise
    code = process.returncode
    return subprocess.CompletedProcess(command, 128 - code if code < 0 else code, stdout, stderr)

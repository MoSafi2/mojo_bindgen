"""Content-addressed Mojo builds shared by native and differential runners."""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "mojo/build/native-testing"
NATIVE = ROOT / "mojo/.pixi/envs/default"
STABLE = ROOT / "mojo/.pixi/envs/stable-tests"
TARGET_CPU = "x86-64-v3"


@contextlib.contextmanager
def cache_guard(*, clean=False):
    BUILD.mkdir(parents=True, exist_ok=True)
    with (BUILD / ".sessions.lock").open("w") as lock:
        if clean:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError(
                    "cache is in use; wait for other runners before clearing it"
                ) from error
            import shutil

            for name in ("binaries", "compiler-cache", "uncached"):
                path = BUILD / name
                if path.is_symlink():
                    raise RuntimeError(f"refusing to clear cache symlink {path}")
                shutil.rmtree(path, ignore_errors=True)
        fcntl.flock(lock, fcntl.LOCK_SH)
        yield


@dataclasses.dataclass
class ProcessResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool = False


def execute(argv, *, env=None, cwd=ROOT, timeout=300) -> ProcessResult:
    start = time.monotonic()
    try:
        process = subprocess.Popen(
            list(map(str, argv)),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as error:
        raise RuntimeError(f"cannot execute {argv[0]}: {error}") from error
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        expired = False
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        expired = True
    return ProcessResult(
        list(map(str, argv)), process.returncode, stdout, stderr, time.monotonic() - start, expired
    )


def environment(prefix=NATIVE, *, scratch=None):
    env = os.environ.copy()
    # Never carry another SDK's loader paths into this compiler or executable.
    env["CONDA_PREFIX"] = str(prefix)
    env["MODULAR_HOME"] = str(prefix / "share/max")
    env["PATH"] = str(prefix / "bin") + os.pathsep + os.environ.get("PATH", "")
    env["LD_LIBRARY_PATH"] = str(prefix / "lib")
    env.pop("PYTHONPATH", None)
    env["MODULAR_CACHE_DIR"] = str(BUILD / "compiler-cache" / prefix.name)
    if prefix == NATIVE:
        env["MOJO_BINDGEN_CLANG_LIBRARY_PATH"] = str(prefix / "lib/libclang.so")
    else:
        env.pop("MOJO_BINDGEN_CLANG_LIBRARY_PATH", None)
    if scratch is not None:
        Path(scratch).mkdir(parents=True, exist_ok=True)
        env["TMPDIR"] = str(scratch)
    return env


def tree_digest(paths):
    digest = hashlib.sha256()
    for path in sorted(set(map(Path, paths))):
        digest.update(str(path).encode())
        if path.is_file():
            digest.update(path.read_bytes())
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if (
                    child.is_file()
                    and not any(
                        part in {".pixi", "build", "__pycache__"}
                        for part in child.relative_to(path).parts
                    )
                    and (child.suffix in {".mojo", ".🔥", ".mojoc"} or path.name == "conda-meta")
                ):
                    digest.update(str(child.relative_to(path)).encode())
                    digest.update(child.read_bytes())
    return digest.hexdigest()


@dataclasses.dataclass
class Built:
    binary: Path
    cached: bool
    seconds: float


class Builder:
    def __init__(self, *, compile_jobs=2, compiler_threads=1, timeout=600, cache=True):
        self.capacity = threading.Semaphore(compile_jobs)
        self.compiler_threads = compiler_threads
        self.timeout = timeout
        self.cache = cache
        self._identities = {}
        self._identity_lock = threading.Lock()
        self.built = 0
        self.hits = 0
        self._counter_lock = threading.Lock()

    def identity(self, prefix):
        with self._identity_lock:
            if prefix not in self._identities:
                compiler = prefix / "bin/mojo"
                if not compiler.is_file():
                    raise RuntimeError(
                        f"missing compiler {compiler}; install mojo/pixi.toml environments"
                    )
                probe = execute([compiler, "--version"], env=environment(prefix), timeout=30)
                if probe.returncode or probe.timed_out:
                    raise RuntimeError(probe.stdout + probe.stderr)
                required = "1.3.0.dev2026103105" if prefix == NATIVE else "1.2.0"
                if f"Mojo {required} " not in probe.stdout:
                    raise RuntimeError(f"wrong compiler: expected {required}, got {probe.stdout}")
                self._identities[prefix] = tree_digest(
                    [
                        compiler.resolve(),
                        prefix / "lib/mojo",
                        prefix / "conda-meta",
                        ROOT / "mojo/pixi.lock",
                    ]
                )
            return self._identities[prefix]

    def build(self, source, optimization, *, prefix=NATIVE, include=(), flags=(), werror=True):
        with cache_guard():
            return self._build(
                source, optimization, prefix=prefix, include=include, flags=flags, werror=werror
            )

    def _build(self, source, optimization, *, prefix, include, flags, werror):
        source = Path(source).resolve()
        includes = tuple(map(Path, include))
        args = [
            *(["--Werror"] if werror else []),
            f"-O{optimization}",
            "--target-cpu",
            TARGET_CPU,
            "--num-threads",
            str(self.compiler_threads),
            *flags,
        ]
        for path in includes:
            args += ["-I", str(path.resolve())]
        inputs = [source, *includes]
        # Include helper modules beside the entry point, but not unrelated tests.
        inputs += [p for p in source.parent.glob("*.mojo") if not p.name.startswith("test_")]
        library_dirs = [Path(flag[2:]) for flag in flags if str(flag).startswith("-L")]
        library_names = [str(flag)[2:] for flag in flags if str(flag).startswith("-l")]
        for directory in library_dirs:
            for name in library_names:
                inputs.extend(directory.glob(f"lib{name}.so*"))
                inputs.extend(directory.glob(f"lib{name}.a"))
        input_identity = tree_digest(inputs)
        key = hashlib.sha256(
            (self.identity(prefix) + input_identity + json.dumps([str(source), args])).encode()
        ).hexdigest()
        store = BUILD / "binaries" / key
        store.parent.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        with (store.parent / f"{key}.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            binary, stamp = store / "bin", store / "sha256"
            if self.cache and binary.is_file() and stamp.is_file():
                if hashlib.sha256(binary.read_bytes()).hexdigest() == stamp.read_text():
                    with self._counter_lock:
                        self.hits += 1
                    return Built(binary, True, time.monotonic() - start)
            with (
                self.capacity,
                tempfile.TemporaryDirectory(prefix="build-", dir=store.parent) as directory,
            ):
                stage = Path(directory)
                command = [prefix / "bin/mojo", "build", *args, source, "-o", stage / "bin"]
                result = execute(
                    command, env=environment(prefix, scratch=stage / "tmp"), timeout=self.timeout
                )
                if result.returncode or result.timed_out or not (stage / "bin").is_file():
                    raise RuntimeError(
                        f"compile failed: {' '.join(map(str, command))}\n{result.stdout}{result.stderr}"
                    )
                if tree_digest(inputs) != input_identity:
                    raise RuntimeError(
                        "build inputs changed during compilation; artifact not published"
                    )
                with self._counter_lock:
                    self.built += 1
                if not self.cache:
                    store = BUILD / "uncached" / stage.name
                    store.mkdir(parents=True, exist_ok=True)
                else:
                    store.mkdir(exist_ok=True)
                os.replace(stage / "bin", store / "bin")
                digest = hashlib.sha256((store / "bin").read_bytes()).hexdigest()
                (stage / "stamp").write_text(digest)
                os.replace(stage / "stamp", store / "sha256")
                return Built(store / "bin", False, time.monotonic() - start)


def build_target(kind, optimization, *, builder=None):
    source = (
        ROOT / "mojo/main.mojo"
        if kind == "cli"
        else ROOT / f"tests/mojo/drivers/{kind}_driver.mojo"
    )
    return (
        (builder or Builder())
        .build(source, optimization, include=[ROOT / "mojo", ROOT / "tests/mojo/support"])
        .binary
    )

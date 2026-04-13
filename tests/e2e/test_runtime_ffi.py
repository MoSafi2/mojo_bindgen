"""
End-to-end runtime tests for generated C bindings via Mojo FFI.

Run from repo root:
  pixi run pytest tests/e2e/test_runtime_ffi.py -v -s
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _REPO_ROOT / "tests" / "e2e" / "fixtures"


def _tool_cmd(name: str) -> list[str] | None:
    if shutil.which(name):
        return [name]
    if shutil.which("pixi"):
        return ["pixi", "run", name]
    return None


def _run_checked(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "command failed:\n"
            f"{' '.join(cmd)}\n"
            f"exit={proc.returncode}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def _parse_runner_output(stdout: str) -> dict[str, float | int]:
    out: dict[str, float | int] = {}
    for line in stdout.splitlines():
        if "|" not in line:
            continue
        key, raw = line.split("|", maxsplit=1)
        value_text = raw.strip()
        if any(ch in value_text for ch in (".", "e", "E")):
            out[key.strip()] = float(value_text)
        else:
            out[key.strip()] = int(value_text)
    return out


def _assert_expected(got: dict[str, float | int], expected: dict[str, float | int]) -> None:
    assert got.keys() == expected.keys()
    for key, exp in expected.items():
        got_value = got[key]
        if isinstance(exp, float):
            assert isinstance(got_value, float)
            assert got_value == pytest.approx(exp, rel=1e-12, abs=1e-12), key
        else:
            assert got_value == exp, key


@pytest.mark.skipif(not shutil.which("cc"), reason="requires cc")
@pytest.mark.parametrize("case_name", ["functional_math", "functional_records"])
def test_runtime_ffi_fixture_case(case_name: str, tmp_path: Path) -> None:
    mojo_bindgen = _tool_cmd("mojo-bindgen")
    mojo = _tool_cmd("mojo")
    if mojo_bindgen is None:
        pytest.skip("requires mojo-bindgen (or pixi)")
    if mojo is None:
        pytest.skip("requires mojo (or pixi)")

    case_dir = _FIXTURES / case_name
    header = case_dir / f"{case_name}.h"
    source = case_dir / f"{case_name}.c"
    runner_external = case_dir / "runner_external.mojo"
    runner_dl = case_dir / "runner_dl.mojo"
    cases_path = case_dir / "cases.json"
    expected = json.loads(cases_path.read_text(encoding="utf-8"))

    lib_path = tmp_path / f"lib{case_name}.so"
    _run_checked(["cc", "-shared", "-fPIC", str(source), "-o", str(lib_path)], cwd=_REPO_ROOT)

    bindings_external = tmp_path / f"{case_name}_bindings_external.mojo"
    bindings_dl = tmp_path / f"{case_name}_bindings_dl.mojo"

    _run_checked(
        [
            *mojo_bindgen,
            str(header),
            "--library",
            case_name,
            "--link-name",
            case_name,
            "-o",
            str(bindings_external),
        ],
        cwd=_REPO_ROOT,
    )
    _run_checked(
        [
            *mojo_bindgen,
            str(header),
            "--library",
            case_name,
            "--link-name",
            case_name,
            "--linking",
            "owned_dl_handle",
            "--library-path-hint",
            str(lib_path),
            "-o",
            str(bindings_dl),
        ],
        cwd=_REPO_ROOT,
    )

    external_bin = tmp_path / f"{case_name}_runner_external"
    dl_bin = tmp_path / f"{case_name}_runner_dl"
    _run_checked(
        [
            *mojo,
            "build",
            str(runner_external),
            "-I",
            str(tmp_path),
            "-Xlinker",
            f"-L{tmp_path}",
            "-Xlinker",
            f"-l{case_name}",
            "-o",
            str(external_bin),
        ],
        cwd=_REPO_ROOT,
    )
    _run_checked(
        [
            *mojo,
            "build",
            str(runner_dl),
            "-I",
            str(tmp_path),
            "-o",
            str(dl_bin),
        ],
        cwd=_REPO_ROOT,
    )

    external_env = os.environ.copy()
    external_env["LD_LIBRARY_PATH"] = f"{tmp_path}:{external_env.get('LD_LIBRARY_PATH', '')}".rstrip(":")
    external_result = _run_checked([str(external_bin)], cwd=_REPO_ROOT, env=external_env)
    dl_result = _run_checked([str(dl_bin)], cwd=_REPO_ROOT)

    _assert_expected(_parse_runner_output(external_result.stdout), expected)
    _assert_expected(_parse_runner_output(dl_result.stdout), expected)

"""
Golden end-to-end runtime tests for C -> bindgen -> Mojo execution.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_ROOT = _REPO_ROOT / "tests" / "e2e" / "fixtures"

_PHASES = (
    "bindgen_external",
    "bindgen_dylib_lazy",
    "bindgen_dylib_checked",
    "emit_external",
    "emit_dylib_lazy",
    "emit_dylib_checked",
    "mojo_build_external",
    "mojo_build_dylib_lazy",
    "mojo_build_dylib_checked",
    "runtime_external",
    "runtime_dylib_lazy",
    "runtime_dylib_checked",
)
_VALID_PHASE_STATUS = {
    "pass",
    "known_fail_bindgen",
    "known_fail_mojo",
    "known_fail_abi",
    "unsupported",
    "toolchain_variant",
}


def _tool_cmd(name: str) -> list[str] | None:
    if shutil.which(name):
        return [name]
    if shutil.which("pixi"):
        return ["pixi", "run", name]
    return None


def _run(
    cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def _assert_schema(case_dir: Path, status: dict[str, Any]) -> None:
    phases = status.get("phases")
    assert isinstance(phases, dict), f"{case_dir}: status.json must contain object key 'phases'"
    for phase in _PHASES:
        assert phase in phases, f"{case_dir}: missing phase '{phase}'"
        val = phases[phase]
        assert val in _VALID_PHASE_STATUS, f"{case_dir}: invalid status for {phase}: {val}"

    required = (
        "input.h",
        "impl.c",
        "runner_external.mojo",
        "runner_dylib_lazy.mojo",
        "runner_dylib_checked.mojo",
        "expect.emit.external.mojo",
        "expect.emit.dylib_lazy.mojo",
        "expect.emit.dylib_checked.mojo",
        "expect.runtime.external.json",
        "expect.runtime.dylib_lazy.json",
        "expect.runtime.dylib_checked.json",
    )
    for name in required:
        assert (case_dir / name).exists(), f"{case_dir}: missing required file '{name}'"


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


def _assert_expected_values(got: dict[str, float | int], expected: dict[str, float | int]) -> None:
    assert got.keys() == expected.keys()
    for key, exp in expected.items():
        got_value = got[key]
        if isinstance(exp, float):
            assert isinstance(got_value, float)
            assert got_value == pytest.approx(exp, rel=1e-12, abs=1e-12), key
        else:
            assert got_value == exp, key


def _assert_emit_has_snippets(emitted: str, expectation_file: Path) -> None:
    for raw in expectation_file.read_text(encoding="utf-8").splitlines():
        snippet = raw.strip()
        if not snippet or snippet.startswith("#"):
            continue
        assert snippet in emitted, f"missing snippet '{snippet}' from {expectation_file}"


def _check_phase(
    phase: str,
    expected_status: str,
    proc: subprocess.CompletedProcess[str],
    detail: str,
) -> None:
    ok = proc.returncode == 0
    if expected_status == "pass":
        assert ok, (
            f"{phase} expected pass but failed\n"
            f"{detail}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
        return
    if expected_status.startswith("known_fail") or expected_status in {
        "unsupported",
        "toolchain_variant",
    }:
        if ok:
            pytest.xfail(f"{phase} unexpectedly passed; update status.json and expectations")
        pytest.xfail(f"{phase} expected non-pass ({expected_status})")
        return
    raise AssertionError(f"unknown expected status {expected_status}")


def _persist_generated_bindings(src: Path, dst: Path) -> None:
    if src.exists():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _case_dirs() -> list[Path]:
    return sorted(
        [p for p in _GOLDEN_ROOT.iterdir() if p.is_dir() and (p / "status.json").exists()]
    )


@pytest.mark.skipif(not shutil.which("cc"), reason="requires cc")
@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_golden_runtime_case(case_dir: Path, tmp_path: Path) -> None:
    mojo_bindgen = _tool_cmd("mojo-bindgen")
    mojo = _tool_cmd("mojo")
    if mojo_bindgen is None:
        pytest.skip("requires mojo-bindgen (or pixi)")
    if mojo is None:
        pytest.skip("requires mojo (or pixi)")

    status = json.loads((case_dir / "status.json").read_text(encoding="utf-8"))
    _assert_schema(case_dir, status)
    phases: dict[str, str] = status["phases"]
    case_name = case_dir.name

    header = case_dir / "input.h"
    source = case_dir / "impl.c"
    runner_external = case_dir / "runner_external.mojo"
    runner_dylib_lazy = case_dir / "runner_dylib_lazy.mojo"
    runner_dylib_checked = case_dir / "runner_dylib_checked.mojo"
    expected_rt_external = json.loads(
        (case_dir / "expect.runtime.external.json").read_text(encoding="utf-8")
    )
    expected_rt_dylib_lazy = json.loads(
        (case_dir / "expect.runtime.dylib_lazy.json").read_text(encoding="utf-8")
    )
    expected_rt_dylib_checked = json.loads(
        (case_dir / "expect.runtime.dylib_checked.json").read_text(encoding="utf-8")
    )

    lib_path = tmp_path / f"lib{case_name}.so"
    cc = _run(["cc", "-shared", "-fPIC", str(source), "-o", str(lib_path)], cwd=_REPO_ROOT)
    if cc.returncode != 0:
        raise AssertionError(
            f"failed to build C shared lib for {case_name}\nstdout:\n{cc.stdout}\nstderr:\n{cc.stderr}"
        )

    bindings_external = tmp_path / f"{case_name}_bindings_external.mojo"
    bindings_dylib_lazy = tmp_path / f"{case_name}_bindings_dylib_lazy.mojo"
    bindings_dylib_checked = tmp_path / f"{case_name}_bindings_dylib_checked.mojo"

    bindgen_external = _run(
        [
            *mojo_bindgen,
            str(header),
            "--library",
            case_name,
            "--link-name",
            case_name,
            "--output",
            str(bindings_external),
        ],
        cwd=_REPO_ROOT,
    )
    _check_phase("bindgen_external", phases["bindgen_external"], bindgen_external, str(case_dir))

    bindgen_dylib_lazy = _run(
        [
            *mojo_bindgen,
            str(header),
            "--library",
            case_name,
            "--link-name",
            case_name,
            "--link-mode",
            "dylib-lazy",
            "--library-path",
            str(lib_path),
            "--output",
            str(bindings_dylib_lazy),
        ],
        cwd=_REPO_ROOT,
    )
    _check_phase(
        "bindgen_dylib_lazy", phases["bindgen_dylib_lazy"], bindgen_dylib_lazy, str(case_dir)
    )

    bindgen_dylib_checked = _run(
        [
            *mojo_bindgen,
            str(header),
            "--library",
            case_name,
            "--link-name",
            case_name,
            "--link-mode",
            "dylib-checked",
            "--library-path",
            str(lib_path),
            "--output",
            str(bindings_dylib_checked),
        ],
        cwd=_REPO_ROOT,
    )
    _check_phase(
        "bindgen_dylib_checked",
        phases["bindgen_dylib_checked"],
        bindgen_dylib_checked,
        str(case_dir),
    )

    # Keep generated bindings under each golden case for local inspection.
    _persist_generated_bindings(bindings_external, case_dir / "generated.bindings.external.mojo")
    _persist_generated_bindings(
        bindings_dylib_lazy, case_dir / "generated.bindings.dylib_lazy.mojo"
    )
    _persist_generated_bindings(
        bindings_dylib_checked, case_dir / "generated.bindings.dylib_checked.mojo"
    )

    if bindgen_external.returncode == 0:
        _assert_emit_has_snippets(
            bindings_external.read_text(encoding="utf-8"),
            case_dir / "expect.emit.external.mojo",
        )
    else:
        pytest.xfail("bindgen external did not succeed; emit check skipped")

    if bindgen_dylib_lazy.returncode == 0:
        _assert_emit_has_snippets(
            bindings_dylib_lazy.read_text(encoding="utf-8"),
            case_dir / "expect.emit.dylib_lazy.mojo",
        )
    else:
        pytest.xfail("bindgen dylib-lazy did not succeed; emit check skipped")

    if bindgen_dylib_checked.returncode == 0:
        _assert_emit_has_snippets(
            bindings_dylib_checked.read_text(encoding="utf-8"),
            case_dir / "expect.emit.dylib_checked.mojo",
        )
    else:
        pytest.xfail("bindgen dylib-checked did not succeed; emit check skipped")

    external_bin = tmp_path / f"{case_name}_runner_external"
    dylib_lazy_bin = tmp_path / f"{case_name}_runner_dylib_lazy"
    dylib_checked_bin = tmp_path / f"{case_name}_runner_dylib_checked"

    build_external = _run(
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
    _check_phase(
        "mojo_build_external",
        phases["mojo_build_external"],
        build_external,
        str(case_dir),
    )

    build_dylib_lazy = _run(
        [
            *mojo,
            "build",
            str(runner_dylib_lazy),
            "-I",
            str(tmp_path),
            "-o",
            str(dylib_lazy_bin),
        ],
        cwd=_REPO_ROOT,
    )
    _check_phase(
        "mojo_build_dylib_lazy",
        phases["mojo_build_dylib_lazy"],
        build_dylib_lazy,
        str(case_dir),
    )

    build_dylib_checked = _run(
        [
            *mojo,
            "build",
            str(runner_dylib_checked),
            "-I",
            str(tmp_path),
            "-o",
            str(dylib_checked_bin),
        ],
        cwd=_REPO_ROOT,
    )
    _check_phase(
        "mojo_build_dylib_checked",
        phases["mojo_build_dylib_checked"],
        build_dylib_checked,
        str(case_dir),
    )

    if build_external.returncode == 0:
        external_env = os.environ.copy()
        external_env["LD_LIBRARY_PATH"] = (
            f"{tmp_path}:{external_env.get('LD_LIBRARY_PATH', '')}".rstrip(":")
        )
        # C globals resolved via dlsym require the shared object to be loaded into the
        # process. Mojo's link step does not always add DT_NEEDED for -ltestlib; preload
        # ensures symbols are visible to OwnedDLHandle(...).get_symbol (see globals_consts_runtime).
        if case_name == "globals_consts_runtime":
            external_env["LD_PRELOAD"] = str(lib_path)
        runtime_external = _run([str(external_bin)], cwd=_REPO_ROOT, env=external_env)
        _check_phase(
            "runtime_external",
            phases["runtime_external"],
            runtime_external,
            str(case_dir),
        )
        if runtime_external.returncode == 0:
            _assert_expected_values(
                _parse_runner_output(runtime_external.stdout), expected_rt_external
            )

    if build_dylib_lazy.returncode == 0:
        runtime_dylib_lazy = _run([str(dylib_lazy_bin)], cwd=_REPO_ROOT)
        _check_phase(
            "runtime_dylib_lazy",
            phases["runtime_dylib_lazy"],
            runtime_dylib_lazy,
            str(case_dir),
        )
        if runtime_dylib_lazy.returncode == 0:
            _assert_expected_values(
                _parse_runner_output(runtime_dylib_lazy.stdout), expected_rt_dylib_lazy
            )

    if build_dylib_checked.returncode == 0:
        runtime_dylib_checked = _run([str(dylib_checked_bin)], cwd=_REPO_ROOT)
        _check_phase(
            "runtime_dylib_checked",
            phases["runtime_dylib_checked"],
            runtime_dylib_checked,
            str(case_dir),
        )
        if runtime_dylib_checked.returncode == 0:
            _assert_expected_values(
                _parse_runner_output(runtime_dylib_checked.stdout), expected_rt_dylib_checked
            )

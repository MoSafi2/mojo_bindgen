"""Tests for header path resolution and compile-arg defaults (no libclang required)."""

from __future__ import annotations

import os
import tempfile
import warnings
from pathlib import Path

import pytest

from mojo_bindgen.utils import build_c_parse_args, normalize_std_flag
from mojo_bindgen.parsing.parser import _default_system_compile_args, _resolve_header_path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_absolute_path() -> None:
    p = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
    resolved = _resolve_header_path(p)
    assert resolved.is_file()
    assert resolved == p.resolve()


def test_relative_via_cwd_without_dev() -> None:
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "x.h"
        h.write_text("/* x */\n", encoding="utf-8")
        old = os.getcwd()
        try:
            os.chdir(td)
            r = _resolve_header_path("x.h")
            assert r.resolve() == h.resolve()
        finally:
            os.chdir(old)


def test_relative_header_resolves_from_cwd_only() -> None:
    """Relative paths are resolved against the process cwd (no repo-root magic)."""
    rel = "tests/fixtures/everything.h"
    repo_file = _REPO_ROOT / rel
    assert repo_file.is_file()
    old_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            with pytest.raises(FileNotFoundError) as exc_info:
                _resolve_header_path(rel)
            assert "header not found" in str(exc_info.value)

            r = _resolve_header_path(repo_file)
            assert r.resolve() == repo_file.resolve()
    finally:
        os.chdir(old_cwd)


def test_returns_list_starting_with_usr_include() -> None:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        args = _default_system_compile_args()
    assert isinstance(args, list)
    assert len(args) >= 1
    assert args[0] == "-I/usr/include"
    for x in w:
        assert isinstance(x.message, UserWarning)


def test_normalize_std_flag_accepts_legacy_forms() -> None:
    assert normalize_std_flag("-std=c99") == "-std=c99"
    assert normalize_std_flag("--std=c99") == "-std=c99"
    assert normalize_std_flag("std=c99") == "-std=c99"
    assert normalize_std_flag("-I./include") == "-I./include"


def test_build_c_parse_args_uses_default_std_when_missing() -> None:
    args = build_c_parse_args(["-I./include"], default_std="-std=gnu11")
    assert args == ["-x", "c", "-std=gnu11", "-I./include"]


def test_build_c_parse_args_uses_user_std_and_normalizes() -> None:
    args = build_c_parse_args(
        ["--std=c99", "-I./include"],
        default_std="-std=gnu11",
    )
    assert args == ["-x", "c", "-std=c99", "-I./include"]


def test_build_c_parse_args_accepts_bare_std_equals() -> None:
    args = build_c_parse_args(
        ["std=c17", "-DVALUE=1"],
        default_std="-std=gnu11",
    )
    assert args == ["-x", "c", "-std=c17", "-DVALUE=1"]

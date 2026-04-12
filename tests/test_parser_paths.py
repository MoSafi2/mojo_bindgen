"""Tests for header path resolution and compile-arg defaults (no libclang required)."""

from __future__ import annotations

import os
import tempfile
import warnings
from pathlib import Path

import pytest

from mojo_bindgen.parser import _default_system_compile_args, _resolve_header_path

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


def test_repo_relative_requires_dev_flag() -> None:
    rel = "tests/fixtures/everything.h"
    repo_file = _REPO_ROOT / rel
    assert repo_file.is_file()
    old_cwd = os.getcwd()
    old_dev = os.environ.get("MOJO_BINDGEN_DEV")
    try:
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            if "MOJO_BINDGEN_DEV" in os.environ:
                del os.environ["MOJO_BINDGEN_DEV"]
            with pytest.raises(FileNotFoundError) as exc_info:
                _resolve_header_path(rel)
            assert "MOJO_BINDGEN_DEV" in str(exc_info.value)

            os.environ["MOJO_BINDGEN_DEV"] = "1"
            r = _resolve_header_path(rel)
            assert r.resolve() == repo_file.resolve()
    finally:
        os.chdir(old_cwd)
        if old_dev is None:
            os.environ.pop("MOJO_BINDGEN_DEV", None)
        else:
            os.environ["MOJO_BINDGEN_DEV"] = old_dev


def test_returns_list_starting_with_usr_include() -> None:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        args = _default_system_compile_args()
    assert isinstance(args, list)
    assert len(args) >= 1
    assert args[0] == "-I/usr/include"
    for x in w:
        assert isinstance(x.message, UserWarning)

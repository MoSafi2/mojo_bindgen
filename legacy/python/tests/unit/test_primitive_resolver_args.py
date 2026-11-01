"""Tests for primitive suffix-probe parse-arg composition."""

from __future__ import annotations

from mojo_bindgen.parsing.lowering.literal_resolver import build_c_parse_args


def test_suffix_probe_args_uses_default_std_when_missing() -> None:
    args = build_c_parse_args(["-I/usr/include"])
    assert args == ["-x", "c", "-std=gnu11", "-I/usr/include"]


def test_suffix_probe_args_respects_user_std() -> None:
    args = build_c_parse_args(["--std=c99", "-I/usr/include"])
    assert args == ["-x", "c", "-std=c99", "-I/usr/include"]


def test_suffix_probe_args_accepts_bare_std_equals() -> None:
    args = build_c_parse_args(["std=c17"])
    assert args == ["-x", "c", "-std=c17"]

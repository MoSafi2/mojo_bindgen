"""Helpers for constructing libclang argument lists."""

from __future__ import annotations


def normalize_std_flag(arg: str) -> str:
    """
    Normalize C standard flags to ``-std=...`` form.

    Accepted inputs:
    - ``-std=c99`` (unchanged)
    - ``--std=c99`` (normalized)
    - ``std=c99`` (normalized)
    """
    if arg.startswith("--std="):
        return f"-std={arg[len('--std=') :]}"
    if arg.startswith("std="):
        return f"-{arg}"
    return arg


def build_c_parse_args(
    compile_args: list[str],
    *,
    default_std: str = "-std=gnu11",
) -> list[str]:
    """
    Build parse args for C translation units with predictable std handling.

    User-provided C standard flags take precedence. ``default_std`` is only
    added when no normalized ``-std=...`` flag is present.
    """
    normalized_args = [normalize_std_flag(arg) for arg in compile_args]
    has_std = any(arg.startswith("-std=") for arg in normalized_args)
    prefix = ["-x", "c"]
    if not has_std:
        prefix.append(default_std)
    return prefix + normalized_args

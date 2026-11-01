"""Parser-driven surface goldens for representative headers."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
from tests._paths import ROOT as _SHARED_ROOT
from tests.header_harness import HeaderHarness

_REPO_ROOT = _SHARED_ROOT
_SURFACE_ROOT = _REPO_ROOT / "tests" / "surface" / "fixtures"
_SOURCE_LINE = re.compile(r"^# source: .+$", re.MULTILINE)
_GOLDEN_EMIT_OPTIONS = MojoEmitOptions()
"""Surface goldens track the default generator pipeline output."""


def _case_dirs() -> list[Path]:
    return sorted(p for p in _SURFACE_ROOT.iterdir() if p.is_dir())


def _normalize_source_line(text: str, relative_header: str) -> str:
    return _SOURCE_LINE.sub(f"# source: {relative_header}", text)


def _golden_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if not line.startswith("from ")]


def _assert_golden_subsequence(actual: str, expected: str) -> None:
    actual_lines = _golden_lines(actual)
    start = 0
    for expected_line in _golden_lines(expected):
        try:
            index = actual_lines.index(expected_line, start)
        except ValueError:
            pytest.fail(f"missing expected golden line: {expected_line!r}")
        start = index + 1


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_surface_fixture_external(case_dir: Path, bindgen: HeaderHarness) -> None:
    header = case_dir / "input.h"
    unit = bindgen.parse_header(header, library="surface_globals", link_name="surface_globals")
    out = bindgen.generate(unit, _GOLDEN_EMIT_OPTIONS)
    expected = (case_dir / "expect.external.mojo").read_text(encoding="utf-8")
    relative_header = str(header.relative_to(_REPO_ROOT))
    _assert_golden_subsequence(_normalize_source_line(out, relative_header), expected)

"""Tests for parser-derived target ABI facts on CIR units."""

from __future__ import annotations

from pathlib import Path

from mojo_bindgen.ir import Unit
from mojo_bindgen.parsing.parser import ClangParser


def test_clang_parser_records_target_abi_on_unit(tmp_path: Path) -> None:
    header = tmp_path / "probe.h"
    header.write_text("void *take_ptr(void *p);\n", encoding="utf-8")

    unit = ClangParser(header, library="probe", link_name="probe").run()

    assert unit.target_abi.pointer_size_bytes > 0
    assert unit.target_abi.pointer_align_bytes > 0


def test_unit_json_roundtrip_preserves_target_abi(tmp_path: Path) -> None:
    header = tmp_path / "probe.h"
    header.write_text("int take_int(int value);\n", encoding="utf-8")

    unit = ClangParser(header, library="probe", link_name="probe").run()
    restored = Unit.from_json_dict(unit.to_json_dict())

    assert restored.target_abi == unit.target_abi

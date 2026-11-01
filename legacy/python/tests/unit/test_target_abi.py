"""Tests for parser-derived target ABI facts on CIR units."""

from __future__ import annotations

from pathlib import Path

from mojo_bindgen.ir import ByteOrder
from tests.header_harness import HeaderHarness


def test_clang_parser_records_target_abi_on_unit(tmp_path: Path, bindgen: HeaderHarness) -> None:
    header = tmp_path / "probe.h"
    header.write_text("void *take_ptr(void *p);\n", encoding="utf-8")
    unit = bindgen.parse_header(header, library="probe", link_name="probe")
    assert unit.target_abi.pointer_size_bytes > 0
    assert unit.target_abi.pointer_align_bytes > 0
    assert unit.target_abi.byte_order in (ByteOrder.LITTLE, ByteOrder.BIG)


def test_unit_json_roundtrip_preserves_target_abi(tmp_path: Path, bindgen: HeaderHarness) -> None:
    header = tmp_path / "probe.h"
    header.write_text("int take_int(int value);\n", encoding="utf-8")
    unit = bindgen.parse_header(header, library="probe", link_name="probe")
    restored = bindgen.roundtrip_cir(unit)
    assert restored.target_abi == unit.target_abi
    assert restored.target_abi.byte_order == unit.target_abi.byte_order

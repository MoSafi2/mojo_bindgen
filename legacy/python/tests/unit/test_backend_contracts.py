"""Stage-specific debug decoding rejects malformed inputs and stays reusable."""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

import pytest

from mojo_bindgen.ir import ByteOrder, LinkMode, MojoModule, TargetABI, Unit
from mojo_bindgen.serde import to_debug_dict
from tests.header_harness import HarnessError, HeaderHarness


@pytest.mark.parametrize("stage", ["cir", "mojo"])
@pytest.mark.parametrize("failure", ["unknown-tag", "wrong-stage"])
def test_debug_decoder_failure_preserves_input_and_recovers(
    bindgen: HeaderHarness, stage: Literal["cir", "mojo"], failure: str
) -> None:
    unit = Unit("empty.h", "demo", "demo", TargetABI(8, 8, ByteOrder.LITTLE), ())
    module = MojoModule(
        source_header="empty.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
        decls=(),
    )
    valid = unit if stage == "cir" else module
    other = module if stage == "cir" else unit
    payload = (
        {"kind": "UnknownIRNode", "fields": {}}
        if failure == "unknown-tag"
        else to_debug_dict(other)
    )
    before = deepcopy(payload)
    for _ in range(2):
        with pytest.raises(HarnessError):
            bindgen.decode_debug_ir(payload, stage=stage)
        assert payload == before
        assert bindgen.decode_debug_ir(to_debug_dict(valid), stage=stage) == valid

"""Reject ABI mismatches equally at frontend and constructed-CIR boundaries."""

from dataclasses import replace

import pytest

from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.analysis.pipeline import AnalysisOrchestrator
from mojo_bindgen.ir import (
    ByteOrder,
    CFunctionPtr,
    Function,
    IntKind,
    IntType,
    TargetABI,
)
from mojo_bindgen.parsing.parser import ClangParser
from mojo_bindgen.serde import dumps_cir, loads_cir

ABI = TargetABI(8, 8, ByteOrder.LITTLE, "x86_64-unknown-linux-gnu")
I32 = IntType(IntKind.INT, 4, 4)


def test_calling_convention_query_and_rejection(tmp_path):
    header = tmp_path / "calling.h"
    header.write_text("int plain(int);\nint __attribute__((ms_abi)) other(int);\n")
    unit = ClangParser(header, "test", "test").run()
    functions = [d for d in unit.decls if isinstance(d, Function)]
    assert functions[0].calling_convention is None
    assert functions[1].calling_convention == "WIN64"
    for value in (unit, loads_cir(dumps_cir(unit))):
        with pytest.raises(ValueError, match="unsupported calling convention 'WIN64'"):
            AnalysisOrchestrator().analyze(value)
    good = replace(unit, decls=(functions[0],))
    assert AnalysisOrchestrator().analyze(good)


@pytest.mark.parametrize("convention", ["WIN64", "stdcall", "unknown"])
def test_direct_callback_mapping_rejects_unsupported_abi(convention):
    mapper = MapTypePass(TargetQueries(ABI))
    with pytest.raises(ValueError, match="unsupported calling convention"):
        mapper.run(CFunctionPtr(I32, (), calling_convention=convention))
    assert mapper.run(CFunctionPtr(I32, ()))

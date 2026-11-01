"""Isolated Python reference using the native environment's exact libclang runtime."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from clang import cindex as cx

_SHARED_ROOT = Path(__file__).resolve().parents[4]


def main() -> None:
    root = _SHARED_ROOT
    cx.Config.set_library_file(str(root / "mojo/.pixi/envs/default/lib/libclang.so"))
    if sys.argv[1] == "cli":
        from mojo_bindgen.cli import main as cli_main

        raise SystemExit(cli_main(sys.argv[2:]))

    from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
    from mojo_bindgen.analysis.pipeline import AnalysisOrchestrator
    from mojo_bindgen.codegen.mojo_ir_printer import render_mojo_module
    from mojo_bindgen.layout_tests.generator import render_layout_test_module
    from mojo_bindgen.parsing.parser import ClangParser
    from mojo_bindgen.serde import to_debug_dict

    results = []
    for request in json.loads(Path(sys.argv[1]).read_text()):
        unit = ClangParser(request["header"], "testlib", "testlib", request["flags"]).run()
        modes = {}
        for mode in ("external_call", "owned_dl_handle"):
            analyzed = AnalysisOrchestrator(MojoEmitOptions(linking=mode)).analyze_pipeline(unit)
            modes[mode] = {
                "module": to_debug_dict(analyzed.mojo_module),
                "bindings": render_mojo_module(analyzed.mojo_module),
                "layout": render_layout_test_module(
                    normalized_unit=analyzed.normalized_unit,
                    mojo_module=analyzed.mojo_module,
                    main_module_name="bindings",
                ),
            }
        results.append({"raw": to_debug_dict(unit), "modes": modes})
    Path(sys.argv[2]).write_text(json.dumps(results))


if __name__ == "__main__":
    main()

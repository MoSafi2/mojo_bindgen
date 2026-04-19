"""Generate stress fixture artifacts.

This script regenerates:

- emitted Mojo goldens for emit-enabled stress cases
- annotated IR JSONC files for all stress cases
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mojo_bindgen.codegen.generator import MojoGenerator
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    Array,
    Const,
    Enum,
    Function,
    GlobalVar,
    MacroDecl,
    OpaqueRecordRef,
    Struct,
    Type,
    Typedef,
    TypeRef,
    Unit,
    UnsupportedType,
)
from mojo_bindgen.parsing.parser import ClangParser

REPO_ROOT = Path(__file__).resolve().parents[2]
STRESS_ROOT = REPO_ROOT / "tests" / "stress"


@dataclass(frozen=True)
class StressCase:
    key: str
    header: Path
    library: str
    link_name: str
    emit: bool


CASES = (
    StressCase(
        key="normal/stress_normal",
        header=STRESS_ROOT / "normal" / "stress_normal_input.h",
        library="stress_normal",
        link_name="stress_normal",
        emit=True,
    ),
    StressCase(
        key="normal/stress_globals_consts",
        header=STRESS_ROOT / "normal" / "stress_globals_consts_input.h",
        library="stress_globals_consts",
        link_name="stress_globals_consts",
        emit=True,
    ),
    StressCase(
        key="weird/stress_weird",
        header=STRESS_ROOT / "weird" / "stress_weird_input.h",
        library="stress_weird",
        link_name="stress_weird",
        emit=False,
    ),
    StressCase(
        key="weird/stress_extensions",
        header=STRESS_ROOT / "weird" / "stress_extensions_input.h",
        library="stress_extensions",
        link_name="stress_extensions",
        emit=False,
    ),
    StressCase(
        key="weird/stress_macros",
        header=STRESS_ROOT / "weird" / "stress_macros_input.h",
        library="stress_macros",
        link_name="stress_macros",
        emit=False,
    ),
)


def _relative_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _normalize_source_line(text: str, header: Path) -> str:
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        if line.startswith("# source: "):
            out.append(f"# source: {_relative_path(header)}")
        else:
            out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _decl_comment(decl: object) -> str:
    if isinstance(decl, Struct):
        if not decl.is_complete:
            kind = "union" if decl.is_union else "struct"
            return f"incomplete {kind} declaration"
        if decl.is_union:
            return f"complete union declaration size={decl.size_bytes} align={decl.align_bytes}"
        return f"complete struct declaration size={decl.size_bytes} align={decl.align_bytes}"
    if isinstance(decl, Typedef):
        return f"typedef declaration {decl.name}"
    if isinstance(decl, Function):
        return f"function declaration with {len(decl.params)} parameter(s)"
    if isinstance(decl, Enum):
        return f"enum declaration with {len(decl.enumerants)} enumerant(s)"
    if isinstance(decl, Const):
        return "constant declaration"
    if isinstance(decl, MacroDecl):
        return f"macro declaration kind={decl.kind}"
    if isinstance(decl, GlobalVar):
        return "global variable declaration"
    return type(decl).__name__


def _type_comment(t: Type) -> str:
    if isinstance(t, TypeRef):
        return f"typedef reference {t.name}"
    if isinstance(t, OpaqueRecordRef):
        kind = "union" if t.is_union else "struct"
        return f"pointer-target opaque {kind} {t.name}"
    if isinstance(t, UnsupportedType):
        return f"unsupported type category={t.category}"
    if isinstance(t, Array):
        return f"{t.array_kind} array"
    return type(t).__name__


def _iter_jsonc_lines(unit: Unit, data: dict[str, Any]) -> list[str]:
    lines: list[str] = ["{"]
    lines.append(f'  "kind": {json.dumps(data["kind"])},')
    lines.append(f'  "source_header": {json.dumps(_relative_path(Path(data["source_header"])))},')
    lines.append(f'  "library": {json.dumps(data["library"])},')
    lines.append(f'  "link_name": {json.dumps(data["link_name"])},')
    lines.append('  "decls": [')
    for index, (decl, decl_data) in enumerate(zip(unit.decls, data["decls"], strict=True)):
        comment = _decl_comment(decl)
        lines.append(f"    // {comment}")
        pretty = json.dumps(decl_data, indent=2)
        pretty_lines = pretty.splitlines()
        for i, raw in enumerate(pretty_lines):
            suffix = "," if i == len(pretty_lines) - 1 and index != len(data["decls"]) - 1 else ""
            lines.append(f"    {raw}{suffix}")
        if isinstance(decl, Struct):
            for field in decl.fields:
                lines.append(
                    f"    // field {field.source_name or field.name or '(anonymous)'}: {_type_comment(field.type)}"
                )
        elif isinstance(decl, Function):
            for param in decl.params:
                lines.append(
                    f"    // param {param.name or '(anonymous)'}: {_type_comment(param.type)}"
                )
        elif isinstance(decl, Const):
            lines.append(f"    // const expr kind: {type(decl.expr).__name__}")
        elif isinstance(decl, MacroDecl):
            body = " ".join(decl.tokens) if decl.tokens else "(empty)"
            lines.append(f"    // macro body: {body}")
            if decl.expr is not None:
                lines.append(f"    // macro expr kind: {type(decl.expr).__name__}")
            if decl.diagnostic is not None:
                lines.append(f"    // macro diagnostic: {decl.diagnostic}")
        elif isinstance(decl, GlobalVar):
            lines.append(f"    // global type: {_type_comment(decl.type)}")
    lines.append("  ],")
    lines.append('  "diagnostics": [')
    for index, diag in enumerate(data["diagnostics"]):
        if "decl_id" in diag and diag["decl_id"]:
            lines.append(f"    // diagnostic for {diag['decl_id']}")
        pretty = json.dumps(diag, indent=2)
        pretty_lines = pretty.splitlines()
        for i, raw in enumerate(pretty_lines):
            suffix = (
                "," if i == len(pretty_lines) - 1 and index != len(data["diagnostics"]) - 1 else ""
            )
            lines.append(f"    {raw}{suffix}")
    lines.append("  ]")
    lines.append("}")
    return lines


def _write_case(case: StressCase, *, ir_only: bool) -> None:
    unit = ClangParser(case.header, library=case.library, link_name=case.link_name).run()
    base = case.header.parent / case.key.split("/")[-1]

    if case.emit and not ir_only:
        external = MojoGenerator(MojoEmitOptions()).generate(unit)
        (base.parent / f"{base.name}_external.mojo").write_text(
            _normalize_source_line(external, case.header),
            encoding="utf-8",
        )
        no_align = MojoGenerator(MojoEmitOptions(emit_align=False)).generate(unit)
        (base.parent / f"{base.name}_no_align.mojo").write_text(
            _normalize_source_line(no_align, case.header),
            encoding="utf-8",
        )

    data = unit.to_json_dict()
    jsonc_text = "\n".join(_iter_jsonc_lines(unit, data)) + "\n"
    (base.parent / f"{base.name}_ir.jsonc").write_text(jsonc_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--ir-only", action="store_true")
    args = parser.parse_args()

    selected = [case for case in CASES if not args.case or case.key in args.case]
    for case in selected:
        _write_case(case, ir_only=args.ir_only)


if __name__ == "__main__":
    main()

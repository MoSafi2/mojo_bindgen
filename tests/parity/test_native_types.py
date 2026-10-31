"""Differential acceptance for the recursive native type-mapping library."""

from __future__ import annotations

import copy
import json
import os
import random
import subprocess
from pathlib import Path

import pytest

from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    AtomicType,
    BuiltinType,
    ByteOrder,
    CArray,
    CFunctionPtr,
    ComplexType,
    Const,
    ConstArg,
    CParam,
    CPointer,
    CType,
    DocComment,
    DTypeArg,
    Enum,
    EnumRef,
    FloatKind,
    FloatType,
    Function,
    GlobalVar,
    IntKind,
    IntType,
    MacroDecl,
    MojoArray,
    MojoBuiltin,
    MojoFunctionPtr,
    MojoParam,
    MojoPointer,
    NameArg,
    NamedType,
    OpaqueRecordRef,
    ParametricBase,
    ParametricType,
    PointerMutability,
    PointerOrigin,
    QualifiedType,
    Qualifiers,
    Struct,
    StructRef,
    TargetABI,
    TypeArg,
    Typedef,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)
from mojo_bindgen.parsing.parser import ClangParser
from mojo_bindgen.serde import decode_c_type, decode_mojo_type, to_debug_dict

pytestmark = [pytest.mark.expensive, pytest.mark.integration]
ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "mojo/pixi.toml"
ABI = TargetABI(8, 8, ByteOrder.LITTLE, "x86_64-unknown-linux-gnu")


@pytest.fixture(scope="module", params=[0, 3], ids=["O0", "O3"])
def native_driver(request, tmp_path_factory):
    directory = tmp_path_factory.mktemp(f"native-types-o{request.param}")
    executable = directory / "type-mapping-driver"
    subprocess.run(
        [
            "pixi",
            "run",
            "--manifest-path",
            str(MANIFEST),
            "--locked",
            "mojo",
            "build",
            "-I",
            str(ROOT / "mojo"),
            f"-O{request.param}",
            str(ROOT / "tests/mojo/type_mapping_driver.mojo"),
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = (
        str(ROOT / "mojo/.pixi/envs/default/lib")
        + os.pathsep
        + environment.get("LD_LIBRARY_PATH", "")
    )

    def run(requests, *, ensure_ascii=True):
        source = directory / "requests.json"
        source.write_text(json.dumps(requests, ensure_ascii=ensure_ascii), encoding="utf-8")
        completed = subprocess.run(
            [str(executable), str(source)],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        results = [json.loads(line) for line in completed.stdout.split("\n") if line]
        assert len(results) == len(requests)
        return results

    return run


def _request(t: CType, abi: TargetABI = ABI):
    return {"action": "map", "type": to_debug_dict(t), "target_abi": to_debug_dict(abi)}


def _compare(native_driver, cases, *, ensure_ascii=True):
    requests = [_request(t, abi) for t, abi in cases]
    before = copy.deepcopy(requests)
    actual = native_driver(requests, ensure_ascii=ensure_ascii)
    assert requests == before
    for index, ((source, abi), result) in enumerate(zip(cases, actual, strict=True)):
        try:
            mapped = MapTypePass(TargetQueries(abi)).run(source)
        except ValueError as error:
            assert "error" in result, (index, source, result)
            assert result["error"] == str(error), (index, source, result)
        else:
            assert result.get("source") == to_debug_dict(source), (index, source, result)
            assert result.get("mapped") == to_debug_dict(mapped), (index, source, result)
            assert decode_c_type(result["source"]) == source
            assert decode_mojo_type(result["mapped"]) == mapped


def _catalog():
    scalar = IntType(IntKind.INT, 4, 4)
    floats = [
        FloatType(kind, size, size) for kind, size in zip(FloatKind, [2, 4, 8, 16, 16], strict=True)
    ]
    result: list[CType] = [
        IntType(kind, width, width) for kind in IntKind for width in (0, 1, 2, 4, 8, 16, 3)
    ]
    result += floats
    result.append(VoidType())
    result += [
        CPointer(None),
        CPointer(VoidType()),
        OpaqueRecordRef("opaque", "FILE", "FILE"),
        StructRef("node", "node", "node", size_bytes=16, align_bytes=8),
        EnumRef("enum", "kind", "kind", scalar),
        TypeRef("alias", "size_t", scalar),
    ]
    for const in (False, True):
        for volatile in (False, True):
            for restrict in (False, True):
                q = QualifiedType(scalar, Qualifiers(const, volatile, restrict))
                result += [q, CPointer(q), CPointer(QualifiedType(VoidType(), q.qualifiers))]
    for kind in ("fixed", "incomplete", "flexible", "variable"):
        for size in (None, 0, 1, 3):
            result.append(CArray(CPointer(scalar), size, kind, 24, 8))
    for element in [
        *floats,
        scalar,
        TypeRef("alias", "alias", scalar),
        CPointer(scalar),
        UnsupportedType("unknown", "?", "unsupported"),
    ]:
        for size, align in [(None, None), (4, 4), (16, 16), (0, 0)]:
            result.append(AtomicType(element, size, align))
        for count in (None, 0, 1, 4):
            result.append(VectorType(element, count, 16, True, 16))
    result += [ComplexType(f, f.size_bytes * 2, f.align_bytes) for f in floats]
    for size in (None, 0, -1, 9):
        result.append(
            UnsupportedType("unsupported_extension", "_Extension", "unsupported", size, 8)
        )
    for convention in (None, "", "c", "stdcall", "unexposed"):
        for names in (None, (), ("return",), ("π", "second", "unused")):
            callback = CFunctionPtr(
                CPointer(scalar),
                (
                    CParam("source", scalar, DocComment("/** π */", "π")),
                    CParam("cb", CPointer(scalar)),
                ),
                names,
                True,
                convention,
                True,
                8,
                8,
            )
            result += [callback, CFunctionPtr(scalar, (CParam("nested", callback),))]
    result += [
        TypeRef("name", name, scalar)
        for name in [
            "",
            " ",
            "def",
            "std",
            "123",
            "²x",
            "９x",
            "é_三",
            "a\u0301",
            "a😀b",
            "\u2003π\u00a0",
            'quote"slash\\\n',
        ]
    ]
    # Deterministic nested composition exercises combinations, not only individual families.
    rng = random.Random(20261031)
    for _ in range(100):
        t = rng.choice(result)
        for _ in range(rng.randrange(1, 5)):
            match rng.randrange(4):
                case 0:
                    t = CPointer(t, 8, 8)
                case 1:
                    t = CArray(
                        t, rng.choice([None, 0, 4]), rng.choice(["fixed", "flexible", "variable"])
                    )
                case 2:
                    t = QualifiedType(t, Qualifiers(is_const=True))
                case 3:
                    t = CFunctionPtr(t, (CParam("shared", t),), ("arg",))
        result.append(t)
    return result


def test_every_source_family_matches_python(native_driver):
    triples = [
        None,
        "x86_64-unknown-linux-gnu",
        "aarch64-unknown-linux-gnu",
        "arm-linux-gnueabi",
        "thumbv7-linux",
        "aarch64-apple-darwin",
    ]
    cases = [
        (t, TargetABI(8, 8, ByteOrder.LITTLE, triple)) for t in _catalog() for triple in triples
    ]
    _compare(native_driver, cases)


def test_parsed_fixture_type_slots_match_python(native_driver):
    cases = []
    headers = sorted((ROOT / "tests/corpus/headers").glob("*/input.h"))
    headers += sorted((ROOT / "tests/surface/fixtures").glob("*/input.h"))
    headers += sorted((ROOT / "tests/stress/fixtures").glob("*/input.h"))
    headers += sorted((ROOT / "tests/e2e/fixtures").glob("*/input.h"))
    for header in headers:
        unit = ClangParser(header, library="parity", link_name="parity").run()
        for decl in unit.decls:
            match decl:
                case Function():
                    types = [decl.ret, *(p.type for p in decl.params)]
                case Struct():
                    types = [f.type for f in decl.fields]
                case Typedef():
                    types = [decl.aliased, decl.canonical]
                case Enum():
                    types = [decl.underlying]
                case Const() | GlobalVar():
                    types = [decl.type]
                case MacroDecl():
                    types = [] if decl.type is None else [decl.type]
            cases.extend((t, unit.target_abi) for t in types)
    assert len(headers) >= 30
    assert len(cases) >= 300
    _compare(native_driver, cases)


def test_target_family_roundtrips_and_rejects_wrong_stages(native_driver):
    scalar = BuiltinType(MojoBuiltin.C_INT)
    types = [
        *(BuiltinType(v) for v in MojoBuiltin),
        NamedType("é三"),
        MojoArray(scalar, 0),
        MojoPointer(None),
        MojoPointer(scalar, PointerMutability.IMMUT, PointerOrigin.ANY, True),
        MojoFunctionPtr(
            scalar, (MojoParam("π", scalar, DocComment("text")),), "stdcall", False, True
        ),
        *(
            ParametricType(
                base,
                (
                    DTypeArg("DType.int32"),
                    ConstArg(-2),
                    NameArg("name"),
                    TypeArg(MojoPointer(scalar)),
                ),
            )
            for base in ParametricBase
        ),
    ]
    requests = [{"action": "mojo-roundtrip", "type": to_debug_dict(t)} for t in types]
    for t, result in zip(types, native_driver(requests), strict=True):
        assert result == {"mapped": to_debug_dict(t)}
    bad = [
        {"action": "map", "type": to_debug_dict(scalar), "target_abi": to_debug_dict(ABI)},
        {"action": "mojo-roundtrip", "type": to_debug_dict(IntType(IntKind.INT, 4))},
        {
            "action": "c-roundtrip",
            "type": {"kind": "CPointer", "fields": {"pointee": to_debug_dict(scalar)}},
        },
        {
            "action": "mojo-roundtrip",
            "type": {
                "kind": "MojoArray",
                "fields": {"element": to_debug_dict(IntType(IntKind.INT, 4)), "size": 3},
            },
        },
        {"action": "c-roundtrip", "type": {"kind": "Unknown", "fields": {}}},
        {"action": "c-roundtrip", "type": {"kind": "VoidType", "fields": {"extra": 1}}},
        {
            "action": "c-roundtrip",
            "type": {"kind": "IntType", "fields": {"int_kind": "INT", "size_bytes": True}},
        },
        {
            "action": "c-roundtrip",
            "type": {"kind": "IntType", "fields": {"int_kind": "invalid", "size_bytes": 4}},
        },
        {"action": "c-roundtrip", "type": {"kind": "CPointer", "fields": {}}},
    ]
    bad.append({"action": "c-roundtrip", "type": {"kind": "VoidType", "fields": {"": 1}}})
    bad.append(
        {
            "action": "c-roundtrip",
            "type": {"kind": "CPointer", "fields": {"pointee": None, "size_bytes|align_bytes": 8}},
        }
    )
    assert all("error" in result for result in native_driver(bad))
    defaults = {"kind": "IntType", "fields": {"int_kind": "INT", "size_bytes": 4}}
    assert native_driver([{"action": "c-roundtrip", "type": defaults}]) == [
        {"source": to_debug_dict(IntType(IntKind.INT, 4))}
    ]


def test_unicode_normalization_and_utf8_json(native_driver):
    # Check all classification range transitions, including newly assigned Unicode characters.
    codepoints = set(range(128))
    for predicate in (str.isalnum, str.isdigit, str.isspace):
        previous = False
        for cp in range(0x110000):
            current = predicate(chr(cp))
            if current != previous:
                codepoints.update([cp, max(0, cp - 1)])
            previous = current
    names = [chr(cp) + "x" for cp in sorted(codepoints) if not 0xD800 <= cp <= 0xDFFF]
    names += [chr(cp) + "π" + chr(cp) for cp in range(0x110000) if chr(cp).isspace()]
    cases = [(TypeRef("unicode", name, IntType(IntKind.INT, 4)), ABI) for name in names]
    _compare(native_driver, cases)
    _compare(native_driver, cases, ensure_ascii=False)


@pytest.mark.parametrize(
    "source",
    ["mapping_target_as_source.mojo", "source_child_in_target.mojo", "missing_type_case.mojo"],
)
def test_native_compiler_enforces_stage_and_dispatch_contracts(source, tmp_path):
    completed = subprocess.run(
        [
            "pixi",
            "run",
            "--manifest-path",
            str(MANIFEST),
            "--locked",
            "mojo",
            "build",
            "-I",
            str(ROOT / "mojo"),
            str(ROOT / "tests/mojo/compile_fail" / source),
            "-o",
            str(tmp_path / "invalid"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "error:" in completed.stderr
    assert (
        "CType" in completed.stderr
        or "MojoType" in completed.stderr
        or "return" in completed.stderr
    )

"""Optional maintenance plugin: capture passing Python assertions as native fixtures.

Run explicitly through pytest's plugin API. Results are staged under mojo/build;
review and merge them with the existing fixture inventory, never from native output.
"""

import copy
import dataclasses
import gzip
import hashlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import tests.header_harness as harness
from mojo_bindgen.codegen.mojo_ir_printer import MojoIRPrintOptions
from mojo_bindgen.serde import to_debug_dict

ROOT = Path(__file__).resolve().parents[3]
DEST = ROOT / "mojo/build/reference-refresh"
CATALOG = json.loads((ROOT / "tests/mojo/fixtures/inventory.json").read_text())


def normalized_id(value):
    return value.replace("legacy/python/", "").replace("[python-", "[").replace("[python]", "")


BY_ID = {normalized_id(item["id"]): item for item in CATALOG}
DEST.mkdir(parents=True, exist_ok=True)
current = None
inventory = []
ffi_setup = {}
real_run = subprocess.run


def payload(value):
    if dataclasses.is_dataclass(value):
        return to_debug_dict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): payload(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [payload(x) for x in value]
    return value


def opts(value):
    v = value or harness.MojoEmitOptions()
    return {
        key: payload(getattr(v, key))
        for key in (
            "linking",
            "strict_abi",
            "module_comment",
            "emit_doc_comments",
            "warn_abi",
            "ffi_origin",
            "library_path_hint",
        )
        if getattr(v, key) is not None
    }


Original = harness.PythonHeaderHarness


class Recorded(Original):
    def record(self, request, callback, key, encode=payload):
        try:
            value = callback()
        except (ValueError, TypeError, harness.HarnessError, harness.HeaderParseError):
            current["operations"].append({"request": payload(request), "expected_error": True})
            raise
        current["operations"].append(
            {"request": payload(request), "expected": {key: encode(value)}}
        )
        return value

    def parse_header(self, header, **kw):
        request = {
            "action": "parse-header",
            "header": str(header),
            **{k: payload(v) for k, v in kw.items() if k != "clang_macro_fallback_build_dir"},
        }
        return self.record(
            request, lambda: super(Recorded, self).parse_header(header, **kw), "unit"
        )

    def generate(self, unit, options=None):
        return self.record(
            {"action": "generate", "unit": payload(unit), **opts(options)},
            lambda: super(Recorded, self).generate(unit, options),
            "bindings",
        )

    def map_unit(self, unit, *, options=None):
        return self.record(
            {"action": "map-unit", "unit": payload(unit), **opts(options)},
            lambda: super(Recorded, self).map_unit(unit, options=options),
            "module",
        )

    def analyze(self, unit):
        return self.record(
            {"action": "analyze", "unit": payload(unit)},
            lambda: super(Recorded, self).analyze(unit),
            "module",
        )

    def map_expr(self, expr, *, target_abi):
        return self.record(
            {"action": "map-expr", "expr": payload(expr), "target_abi": payload(target_abi)},
            lambda: super(Recorded, self).map_expr(expr, target_abi=target_abi),
            "expr",
        )

    def fold_expr(self, expr):
        return self.record(
            {"action": "fold", "expr": payload(expr)},
            lambda: super(Recorded, self).fold_expr(expr),
            "expr",
        )

    def normalize(self, module):
        return self.record(
            {"action": "normalize", "module": payload(module)},
            lambda: super(Recorded, self).normalize(module),
            "module",
        )

    def render(self, module, options=None):
        v = options or MojoIRPrintOptions()
        return self.record(
            {
                "action": "render",
                "module": payload(module),
                "module_comment": v.module_comment,
                "emit_doc_comments": v.emit_doc_comments,
            },
            lambda: super(Recorded, self).render(module, options),
            "bindings",
        )

    def layout_checks(self, **kw):
        return self.record(
            {
                "action": "layout",
                "unit": payload(kw["normalized_unit"]),
                "module": payload(kw["mojo_module"]),
                "main_module_name": "bindings",
            },
            lambda: super(Recorded, self).layout_checks(**kw),
            "checks",
            lambda v: [
                {"record_name": r.record_name, "checks": [dataclasses.asdict(c) for c in r.checks]}
                for r in v
            ],
        )

    def render_layout(self, **kw):
        return self.record(
            {
                "action": "layout",
                "unit": payload(kw["normalized_unit"]),
                "module": payload(kw["mojo_module"]),
                "main_module_name": kw["main_module_name"],
            },
            lambda: super(Recorded, self).render_layout(**kw),
            "layout",
        )

    def expand_macros(self, tokens, environment, *, max_expansion_steps=10000):
        return self.record(
            {
                "action": "expand-macros",
                "tokens": tokens,
                "environment": environment,
                "max_expansion_steps": max_expansion_steps,
            },
            lambda: super(Recorded, self).expand_macros(
                tokens, environment, max_expansion_steps=max_expansion_steps
            ),
            "tokens",
        )

    def macro_environment(self, header, **kw):
        return self.record(
            {"action": "macro-environment", "header": str(header), **kw},
            lambda: super(Recorded, self).macro_environment(header, **kw),
            "environment",
        )

    def roundtrip_cir(self, unit):
        return self.record(
            {"action": "roundtrip-cir", "unit": payload(unit)},
            lambda: super(Recorded, self).roundtrip_cir(unit),
            "unit",
        )

    def decode_debug_ir(self, value, *, stage):
        key = "unit" if stage == "cir" else "module"
        return self.record(
            {"action": "roundtrip-cir" if stage == "cir" else "roundtrip-mojo", key: value},
            lambda: super(Recorded, self).decode_debug_ir(value, stage=stage),
            key,
        )


def run(command, *a, **kw):
    result = real_run(command, *a, **kw)
    if current is None or not isinstance(command, (list, tuple)):
        return result
    command = list(map(str, command))
    if any("-print-file-name=" in x for x in command) or "-E" in command:
        return result
    caller = inspect.stack()[1].filename
    if "/tests/" not in caller:
        return result
    if command[:4] == [sys.executable, "-I", "-m", "mojo_bindgen.cli"]:
        role = "native-cli"
        args = command[4:]
    elif command[:3] == [sys.executable, "-m", "mojo_bindgen.cli"]:
        role = "native-cli"
        args = command[3:]
    elif Path(command[0]).name in ("cc", "gcc", "clang"):
        role = "cc"
        args = command[1:]
    elif Path(command[0]).name == "mojo":
        role = "stable"
        args = command[1:]
    elif command[0] == "pixi" and command[1:3] == ["run", "mojo"]:
        role = "stable"
        args = command[3:]
    elif command[0].startswith("/tmp/") or "/mojo/build/test-tmp/" in command[0]:
        role = "program"
        args = command
    else:
        return result
    env = kw.get("env") or os.environ
    delta = {k: v for k, v in env.items() if k.startswith("MOJO_BINDGEN_") or k in ("LD_PRELOAD",)}
    if kw.get("env") is not None:
        # Keep only fixture paths, never the developer SDK's loader path.
        delta["LD_LIBRARY_PATH"] = ":".join(
            x for x in env.get("LD_LIBRARY_PATH", "").split(":") if "/pytest-" in x
        )
    current["steps"].append(
        {
            "role": role,
            "args": args,
            "env": delta,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    return result


def pytest_configure(config):
    import clang.cindex as cx

    cx.Config.set_library_file(str(ROOT / "mojo/.pixi/envs/default/lib/libclang.so"))
    harness.PythonHeaderHarness = Recorded
    subprocess.run = run


def pytest_runtest_setup(item):
    global current
    current = {"id": item.nodeid, "operations": [], "steps": []}


def pytest_runtest_call(item):
    if "ffi_root" in item.funcargs:
        path = str(item.funcargs["ffi_root"])
        if path not in ffi_setup:
            ffi_setup[path] = copy.deepcopy(current)
        else:
            current["operations"][:0] = copy.deepcopy(ffi_setup[path]["operations"])
            current["steps"][:0] = copy.deepcopy(ffi_setup[path]["steps"])


def pytest_runtest_makereport(item, call):
    if (
        call.when != "call"
        or call.excinfo
        or not current
        or not (current["operations"] or current["steps"])
    ):
        return
    old = BY_ID.get(normalized_id(item.nodeid))
    if old is None:
        return
    case = copy.deepcopy(current)
    case["id"] = old["id"]
    roots = []
    for key, value in item.funcargs.items():
        if (
            isinstance(value, Path)
            and not value.is_relative_to(ROOT / "tests")
            and ("pytest-" in str(value))
        ):
            if value not in roots:
                roots.append(value)
    # Find temp fixture directories referenced by a request even when indirect fixtures own them.
    for value in roots:
        value.mkdir(exist_ok=True, parents=True)
    files = {}
    for index, path in enumerate(roots):
        for f in path.rglob("*"):
            if f.is_file() and f.suffix in (".h", ".c", ".mojo", ".json"):
                try:
                    files[f"input-{index}/{f.relative_to(path)}"] = f.read_text()
                except UnicodeDecodeError:
                    pass
    case["files"] = files
    # Associate generated text with files consumed by subsequent compile steps.
    writes = []
    for dest, text in files.items():
        for index, op in enumerate(case["operations"]):
            expected = op.get("expected", {})
            for key in ("bindings", "layout"):
                if expected.get(key) == text:
                    writes.append({"path": dest, "operation": index, "key": key})
        for index, step in enumerate(case["steps"]):
            if step["role"] == "native-cli" and step["stdout"] == text:
                step.setdefault("stdout_files", []).append(dest)
    case["writes"] = writes
    replacements = [(str(root), f"@WORK@/input-{i}") for i, root in enumerate(roots)] + [
        (str(ROOT), "@ROOT@")
    ]

    def substitute(v):
        if isinstance(v, str):
            for a, b in replacements:
                v = v.replace(a, b)
            return v
        if isinstance(v, list):
            return [substitute(x) for x in v]
        if isinstance(v, dict):
            return {k: substitute(x) for k, x in v.items()}
        return v

    case = substitute(case)
    previous_path = ROOT / "tests/mojo/fixtures/acceptance" / old["fixture"]
    previous_bytes = previous_path.read_bytes()
    previous = json.loads(
        gzip.decompress(previous_bytes) if previous_path.suffix == ".gz" else previous_bytes
    )
    if "file_checks" in previous:
        checks = copy.deepcopy(previous["file_checks"])
        for check in checks:
            key = check["path"].removeprefix("@WORK@/")
            if "exact" in check and key in case["files"]:
                check["exact"] = case["files"][key]
        case["file_checks"] = checks
    # Compiler diagnostics carry paths/locations and version-specific boilerplate.
    # Existing tests check rejection and their concrete assertion substrings, captured separately below.
    case["source_assertions"] = inspect.getsource(item.obj)
    case["source_assertions_sha256"] = hashlib.sha256(
        case["source_assertions"].encode()
    ).hexdigest()
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(case["source_assertions"]))
    tokens = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for cmp in ast.walk(node.test):
            if (
                isinstance(cmp, ast.Compare)
                and any(isinstance(op, ast.In) for op in cmp.ops)
                and "result." in ast.unparse(cmp.comparators[0])
            ):
                if isinstance(cmp.left, ast.Constant) and isinstance(cmp.left.value, str):
                    tokens.append(cmp.left.value)
                elif isinstance(cmp.left, ast.Name) and isinstance(
                    item.funcargs.get(cmp.left.id), str
                ):
                    tokens.append(item.funcargs[cmp.left.id])
    case["diagnostics"] = tokens
    case["reference"] = "Python reference; original assertions passed during capture"
    group = old["group"]
    name = old["fixture"].removesuffix(".gz")
    (DEST / group).mkdir(exist_ok=True, parents=True)
    (DEST / name).write_text(
        json.dumps(case, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    )
    inventory.append({"id": old["id"], "fixture": name})


def pytest_sessionfinish(session, exitstatus):
    if exitstatus == 0:
        (DEST / "captured.json").write_text(json.dumps(inventory, indent=2) + "\n")

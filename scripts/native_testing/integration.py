"""External process mechanics; expected outcomes are asserted by Mojo suites."""

from __future__ import annotations

import dataclasses
import gzip
import json
import os
import shutil
from pathlib import Path

from .build import NATIVE, ROOT, STABLE, TARGET_CPU, build_target, environment, execute


def expand(value, work):
    if isinstance(value, str):
        return value.replace("@ROOT@", str(ROOT)).replace("@WORK@", str(work))
    if isinstance(value, list):
        return [expand(x, work) for x in value]
    if isinstance(value, dict):
        return {key: expand(x, work) for key, x in value.items()}
    return value


def prepare_and_run(binary, cases, work, optimization, builder, timeout):
    for case in cases:
        fixture = ROOT / "tests/mojo/fixtures/acceptance" / case["fixture"]
        raw = json.loads(
            gzip.decompress(fixture.read_bytes())
            if fixture.suffix == ".gz"
            else fixture.read_bytes()
        )
        case_work = work / fixture.name.split(".", 1)[0]
        if case_work.exists():
            shutil.rmtree(case_work)
        case_work.mkdir(parents=True)
        (case_work / "fixture.json").write_text(json.dumps(raw, ensure_ascii=True))
        for name, contents in raw["files"].items():
            destination = case_work / name
            if not destination.resolve().is_relative_to(case_work.resolve()):
                raise RuntimeError(f"fixture output escapes workspace: {name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(expand(contents, case_work))
        env = environment(scratch=case_work / "tmp")
        env.update(
            BINDGEN_TEST_ROOT=str(ROOT),
            BINDGEN_TEST_WORK=str(work),
            BINDGEN_TEST_OPT=str(optimization),
        )
        prepared = execute([binary, "--prepare", case["fixture"]], env=env, timeout=timeout)
        if prepared.returncode or prepared.timed_out:
            raise RuntimeError(
                f"preparation failed: {case['id']}\n{prepared.stdout}{prepared.stderr}"
            )
        plan = json.loads((case_work / "plan.json").read_text())
        outcomes = []
        for step in plan:
            role, args = step["role"], step["args"]
            prefix = STABLE if role in ("stable", "program") else NATIVE
            step_env = environment(prefix, scratch=case_work / "tmp")
            step_env.update(step["env"])
            step_env["LD_LIBRARY_PATH"] = (
                str(case_work)
                + os.pathsep
                + str(prefix / "lib")
                + (
                    os.pathsep + step_env["LD_LIBRARY_PATH"]
                    if step_env.get("LD_LIBRARY_PATH")
                    else ""
                )
            )
            for variable in ("MOJO_BINDGEN_LIBRARY_PATH", "MOJO_BINDGEN_MODERNFFI_LIBRARY_PATH"):
                if variable not in step["env"]:
                    step_env.pop(variable, None)
            if role == "native-cli":
                command = [build_target("cli", optimization, builder=builder), *args]
            elif role == "native-compile":
                command = [
                    NATIVE / "bin/mojo",
                    *args,
                    f"-O{optimization}",
                    "--target-cpu",
                    TARGET_CPU,
                    "--num-threads",
                    "1",
                ]
            elif role == "cc":
                compiler = shutil.which("cc")
                if not compiler:
                    raise RuntimeError("missing C compiler")
                command = [compiler, *args]
            elif role == "stable":
                if args[0] != "build":
                    raise RuntimeError(f"unknown stable compiler operation {args}")
                source = next(Path(arg) for arg in args[1:] if arg.endswith(".mojo"))
                output = Path(args[args.index("-o") + 1])
                include, flags = [], []
                i = 1
                while i < len(args):
                    if args[i] == "-I":
                        include.append(Path(args[i + 1]))
                        i += 2
                    elif args[i] == "-o":
                        i += 2
                    elif args[i] == str(source) or args[i] == "--Werror":
                        i += 1
                    else:
                        flags.append(args[i])
                        i += 1
                # Intentional compiler rejection must run on every invocation.
                if step["returncode"] != 0:
                    command = [
                        STABLE / "bin/mojo",
                        *args,
                        "--target-cpu",
                        TARGET_CPU,
                        "--num-threads",
                        "1",
                    ]
                else:
                    built = builder.build(
                        source,
                        3,
                        prefix=STABLE,
                        include=include,
                        flags=flags,
                        werror="--Werror" in args,
                    )
                    shutil.copy2(built.binary, output)
                    outcomes.append(
                        {
                            "returncode": 0,
                            "stdout": "",
                            "stderr": "",
                            "seconds": built.seconds,
                            "cached": built.cached,
                        }
                    )
                    continue
            elif role == "program":
                command = args
            else:
                raise RuntimeError(f"unknown process role {role}")
            with builder.capacity if role in ("cc", "stable", "native-compile") else _unlimited():
                result = execute(command, env=step_env, cwd=step.get("cwd", ROOT), timeout=timeout)
            if result.timed_out or (role != "program" and result.returncode < 0):
                raise RuntimeError(
                    f"process infrastructure failure: {result.argv}\n{result.stderr}"
                )
            outcomes.append(dataclasses.asdict(result))
            for name in step.get("stdout_files", []):
                (case_work / name).write_text(result.stdout)
        (case_work / "processes.json").write_text(json.dumps(outcomes))


class _unlimited:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

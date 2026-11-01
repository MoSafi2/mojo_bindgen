"""Discover TestSuite programs, supervise workers, and report process outcomes."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .build import BUILD, ROOT, Builder, cache_guard, environment, execute
from .integration import prepare_and_run

SUMMARY = re.compile(
    r"^Summary \[.*?\] (\d+) tests run: (\d+) passed , (\d+) failed , (\d+) skipped\s*$", re.M
)
CASE = re.compile(r"^\s+(PASS|FAIL|SKIP) \[.*?\] (test_\w+)\s*$", re.M)


def parse_report(text, *, listing=False):
    text = re.sub(r"\x1b\[[0-9;]*[mK]", "", text)
    summaries = SUMMARY.findall(text)
    cases = CASE.findall(text)
    if len(summaries) != 1:
        raise ValueError("missing or ambiguous TestSuite summary")
    total, passed, failed, skipped = map(int, summaries[0])
    if not total or total != passed + failed + skipped or total != len(cases):
        raise ValueError("empty or incomplete TestSuite report")
    counts = {status: sum(s == status for s, _ in cases) for status in ("PASS", "FAIL", "SKIP")}
    if (passed, failed, skipped) != tuple(counts[s] for s in ("PASS", "FAIL", "SKIP")):
        raise ValueError("TestSuite totals disagree with case outcomes")
    if len({name for _, name in cases}) != total:
        raise ValueError("duplicate TestSuite names")
    if not listing and passed + failed == 0:
        raise ValueError("all selected tests skipped")
    return cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument(
        "--suite",
        choices=["all", "unit", "acceptance", "runtime", "compile-fail", "examples"],
        default="all",
    )
    parser.add_argument("--optimization", choices=["0", "3", "all"], default="all")
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--compile-jobs", type=int, default=min(2, os.cpu_count() or 1))
    parser.add_argument("--compiler-threads", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--compile-timeout", type=int, default=600)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--clean-cache", action="store_true")
    args = parser.parse_args(argv)
    if (
        min(args.jobs, args.compile_jobs, args.compiler_threads, args.timeout, args.compile_timeout)
        < 1
    ):
        parser.error("worker counts and timeouts must be positive")
    try:
        with cache_guard(clean=args.clean_cache):
            return run_session(args, parser)
    except RuntimeError as error:
        parser.error(str(error))


def run_session(args, parser):
    builder = Builder(
        compile_jobs=args.compile_jobs,
        compiler_threads=args.compiler_threads,
        timeout=args.compile_timeout,
        cache=not args.no_cache,
    )
    if args.paths:
        normalized = []
        for item in args.paths:
            file, separator, test = item.partition("::")
            path = Path(file)
            if not path.exists() and not path.is_absolute():
                path = ROOT / path
            normalized.append(str(path.resolve()) + (separator + test if separator else ""))
        args.paths = normalized
        sources = []
        for item in args.paths:
            path = Path(item.split("::", 1)[0])
            if not path.exists() and not path.is_absolute():
                path = ROOT / path
            path = path.resolve()
            sources += [path] if path.is_file() else list(path.rglob("test_*.mojo"))
    else:
        suites = ROOT / "tests/mojo/suites"
        if args.suite == "unit":
            sources = list((ROOT / "tests/mojo/unit").rglob("test_*.mojo"))
        elif args.suite == "all":
            sources = list((ROOT / "tests/mojo/unit").rglob("test_*.mojo")) + list(
                suites.glob("test_*.mojo")
            )
        else:
            selected = {
                "acceptance": ["backend", "frontend", "fixtures", "vectors"],
                "runtime": ["runtime"],
                "compile-fail": ["compiler"],
                "examples": ["examples"],
            }[args.suite]
            sources = [suites / f"test_{name}.mojo" for name in selected]
    sources = sorted(set(sources))
    if any(not path.is_relative_to(ROOT) for path in sources):
        parser.error("test entry points must be inside the checkout")
    if not sources:
        parser.error("no native tests selected")
    profiles = [0, 3] if args.optimization == "all" else [int(args.optimization)]
    run_root = BUILD / "runs" / f"{time.time_ns()}-{os.getpid()}"
    run_root.mkdir(parents=True)
    start = time.monotonic()
    inventory = json.loads((ROOT / "tests/mojo/fixtures/inventory.json").read_text())
    if args.suite == "all" and not args.paths:
        missing = {ROOT / case["native_source"] for case in inventory} - set(sources)
        if missing:
            parser.error(
                f"coverage inventory has missing entry points: {sorted(map(str, missing))}"
            )

    def run(source, opt):
        name = f"{source.relative_to(ROOT)}[O{opt}]"
        logs = run_root / name.replace("/", "_")
        logs.mkdir()
        work = BUILD / "workspaces" / str(source.relative_to(ROOT)).replace("/", "_") / f"O{opt}"
        work.mkdir(parents=True, exist_ok=True)
        lock = (work / ".lock").open("w")
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            built = builder.build(
                source,
                opt,
                include=[
                    ROOT / "mojo",
                    ROOT / "tests/mojo/support",
                    *([ROOT / "tests/mojo"] if source.parent.name == "suites" else []),
                ],
                flags=["-D", "ASSERT=all"],
            )
            selected = [
                item.split("::", 1)[1]
                for item in args.paths
                if "::" in item and (ROOT / item.split("::", 1)[0]).resolve() == source
            ]
            cases = [
                case
                for case in inventory
                if source
                in {
                    ROOT / case["native_source"],
                    ROOT / case.get("original_native_source", case["native_source"]),
                }
                and (not selected or case["native_test"] in selected)
            ]
            prepare_start = time.monotonic()
            if cases and not args.list:
                prepare_and_run(built.binary, cases, work, opt, builder, args.timeout)
            prepare_seconds = time.monotonic() - prepare_start
            env = environment(scratch=work / "tmp")
            env.update(
                BINDGEN_TEST_ROOT=str(ROOT), BINDGEN_TEST_WORK=str(work), BINDGEN_TEST_OPT=str(opt)
            )
            command = [built.binary]
            if args.list:
                command += ["--skip-all"]
            elif selected:
                command += ["--only", *selected]
            result = execute(command, env=env, timeout=args.timeout)
            (logs / "stdout.log").write_text(result.stdout)
            (logs / "stderr.log").write_text(result.stderr)
            if result.timed_out:
                raise RuntimeError("runtime timeout")
            if result.returncode < 0:
                raise RuntimeError(f"runtime signal {-result.returncode}")
            cases = parse_report(result.stdout + "\n" + result.stderr, listing=args.list)
            reported = {name for _, name in cases}
            expected_names = {
                case["native_test"]
                for case in inventory
                if source
                in {
                    ROOT / case["native_source"],
                    ROOT / case.get("original_native_source", case["native_source"]),
                }
            }
            if expected_names and reported != expected_names:
                raise RuntimeError("coverage inventory and TestSuite discovery disagree")
            if result.returncode or any(status == "FAIL" for status, _ in cases):
                raise RuntimeError(result.stdout + result.stderr)
            return {
                "name": name,
                "ok": True,
                "cases": cases,
                "build_seconds": built.seconds,
                "cached": built.cached,
                "prepare_seconds": prepare_seconds,
                "run_seconds": result.seconds,
            }
        except (RuntimeError, ValueError, OSError) as error:
            (logs / "failure.log").write_text(str(error))
            return {"name": name, "ok": False, "error": str(error), "cases": []}
        finally:
            lock.close()

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run, source, opt) for source in sources for opt in profiles]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(("PASS " if result["ok"] else "FAIL ") + result["name"], flush=True)
            if not result["ok"]:
                print(result["error"], flush=True)
    results.sort(key=lambda r: r["name"])
    suite = ET.Element("testsuite", name="native-mojo")
    for result in results:
        if not result["ok"]:
            ET.SubElement(
                ET.SubElement(suite, "testcase", name=result["name"]), "failure"
            ).text = result["error"]
        for status, name in result["cases"]:
            node = ET.SubElement(suite, "testcase", name=f"{result['name']}::{name}")
            if status == "SKIP":
                ET.SubElement(node, "skipped")
            if args.list:
                print(f"{result['name']}::{name}")
    suite.set("tests", str(len(suite)))
    suite.set("failures", str(sum(not r["ok"] for r in results)))
    ET.ElementTree(suite).write(run_root / "junit.xml", encoding="utf-8", xml_declaration=True)
    report = {
        "results": results,
        "built": builder.built,
        "cached": builder.hits,
        "seconds": time.monotonic() - start,
    }
    (run_root / "report.json").write_text(json.dumps(report, indent=2))
    print(
        f"{sum(r['ok'] for r in results)}/{len(results)} suites; builds={builder.built}, cached={builder.hits}; {report['seconds']:.2f}s; {run_root}"
    )
    return int(any(not r["ok"] for r in results))

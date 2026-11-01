"""Coordinator contracts; run with python -I -S scripts/test_native_runner.py."""

import concurrent.futures
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import build
from .runner import parse_report


class ReportTests(unittest.TestCase):
    def report(self, total=2, passed=1, failed=0, skipped=1):
        return (
            "Running 2 tests\n    PASS [ 0.1 ] test_one\n    SKIP [ 0.1 ] test_two\n"
            f"Summary [ 0.2 ] {total} tests run: {passed} passed , {failed} failed , {skipped} skipped\n"
        )

    def test_valid_report(self):
        self.assertEqual(parse_report(self.report()), [("PASS", "test_one"), ("SKIP", "test_two")])

    def test_rejects_empty_truncated_duplicate_and_inconsistent_reports(self):
        for text in (
            "",
            "PASS",
            self.report(total=3),
            self.report(failed=1),
            self.report() + self.report(),
            self.report().replace("test_two", "test_one"),
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_report(text)

    def test_listing_is_the_only_all_skipped_mode(self):
        text = self.report(passed=0, skipped=2).replace("PASS", "SKIP")
        self.assertEqual(len(parse_report(text, listing=True)), 2)
        with self.assertRaises(ValueError):
            parse_report(text)

    def test_ignores_fail_word_in_messages(self):
        self.assertEqual(len(parse_report("message: FAIL expected\n" + self.report())), 2)

    def test_failure_report_is_valid_data(self):
        text = self.report(passed=0, failed=1).replace("PASS", "FAIL")
        self.assertEqual(parse_report(text)[0][0], "FAIL")


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.prefix = self.root / "sdk"
        (self.prefix / "bin").mkdir(parents=True)
        self.counter = self.root / "counter"
        compiler = self.prefix / "bin/mojo"
        compiler.write_text(
            '#!/bin/sh\necho build >> "'
            + str(self.counter)
            + '"\nwhile [ "$1" != "-o" ]; do shift; done\ncp /bin/true "$2"\n'
        )
        compiler.chmod(0o755)
        self.source = self.root / "test_case.mojo"
        self.source.write_text("def main(): pass\n")
        self.override = patch.object(build, "BUILD", self.root / "cache")
        self.override.start()
        self.builder = build.Builder()
        self.builder.identity = lambda prefix: "fake-sdk"

    def tearDown(self):
        self.override.stop()
        self.temporary.cleanup()

    def test_cold_warm_source_flags_and_corrupt_artifact(self):
        one = self.builder.build(self.source, 0, prefix=self.prefix)
        self.assertFalse(one.cached)
        self.assertTrue(self.builder.build(self.source, 0, prefix=self.prefix).cached)
        self.source.write_text("def main(): print(1)\n")
        self.assertFalse(self.builder.build(self.source, 0, prefix=self.prefix).cached)
        self.assertFalse(self.builder.build(self.source, 3, prefix=self.prefix).cached)
        one.binary.write_bytes(b"bad")
        self.source.write_text("def main(): pass\n")
        self.assertFalse(self.builder.build(self.source, 0, prefix=self.prefix).cached)

    def test_entry_points_with_identical_include_trees_have_distinct_keys(self):
        one = self.root / "driver_a.mojo"
        two = self.root / "driver_b.mojo"
        one.write_text("def main(): print(1)\n")
        two.write_text("def main(): print(2)\n")
        first = self.builder.build(one, 0, prefix=self.prefix, include=[self.root])
        second = self.builder.build(two, 0, prefix=self.prefix, include=[self.root])
        self.assertNotEqual(first.binary, second.binary)
        self.assertFalse(second.cached)

    def test_concurrent_builds_publish_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(
                pool.map(lambda _: self.builder.build(self.source, 0, prefix=self.prefix), range(4))
            )
        self.assertEqual(sum(not r.cached for r in results), 1)
        self.assertEqual(self.counter.read_text().count("build"), 1)

    def test_no_cache_always_builds(self):
        self.builder.cache = False
        for _ in range(2):
            self.assertFalse(self.builder.build(self.source, 0, prefix=self.prefix).cached)
        self.assertEqual(self.counter.read_text().count("build"), 2)

    def test_helper_edit_invalidates(self):
        helper = self.root / "helper.mojo"
        helper.write_text("def helper(): pass\n")
        self.builder.build(self.source, 0, prefix=self.prefix)
        helper.write_text("def helper(): print(2)\n")
        self.assertFalse(self.builder.build(self.source, 0, prefix=self.prefix).cached)

    def test_dependency_sdk_target_and_link_inputs_invalidate(self):
        dependency = self.root / "dependency"
        dependency.mkdir()
        module = dependency / "api.mojo"
        module.write_text("def api(): pass\n")
        library = dependency / "libfixture.so"
        library.write_bytes(b"first library")
        options = {
            "prefix": self.prefix,
            "include": [dependency],
            "flags": [f"-L{dependency}", "-lfixture"],
        }
        self.builder.build(self.source, 0, **options)
        self.assertTrue(self.builder.build(self.source, 0, **options).cached)
        module.write_text("def api(): print(1)\n")
        self.assertFalse(self.builder.build(self.source, 0, **options).cached)
        library.write_bytes(b"second library")
        self.assertFalse(self.builder.build(self.source, 0, **options).cached)
        self.builder.identity = lambda prefix: "different-sdk"
        self.assertFalse(self.builder.build(self.source, 0, **options).cached)
        with patch.object(build, "TARGET_CPU", "different-target"):
            self.assertFalse(self.builder.build(self.source, 0, **options).cached)

    def test_inputs_changed_during_build_never_publish(self):
        execute = build.execute

        def mutate(*args, **kwargs):
            result = execute(*args, **kwargs)
            self.source.write_text("def main(): print(42)\n")
            return result

        with patch.object(build, "execute", side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError, "inputs changed"):
                self.builder.build(self.source, 0, prefix=self.prefix)
        self.assertEqual(list((self.root / "cache").rglob("sha256")), [])

    def test_cache_clear_refuses_active_session(self):
        self.builder.build(self.source, 0, prefix=self.prefix)
        with build.cache_guard(), self.assertRaisesRegex(RuntimeError, "cache is in use"):
            with build.cache_guard(clean=True):
                self.fail("active cache was cleared")
        self.assertTrue(self.builder.build(self.source, 0, prefix=self.prefix).cached)

    def test_failed_compile_never_publishes(self):
        compiler = self.prefix / "bin/mojo"
        compiler.write_text("#!/bin/sh\nexit 2\n")
        for _ in range(2):
            with self.assertRaisesRegex(RuntimeError, "compile failed"):
                self.builder.build(self.source, 0, prefix=self.prefix)
        self.assertEqual(list((self.root / "cache").rglob("sha256")), [])


class ProcessTests(unittest.TestCase):
    def test_deadline_kills_process_group(self):
        result = build.execute(
            [sys.executable, "-I", "-S", "-c", "import time;time.sleep(20)"], timeout=0.05
        )
        self.assertTrue(result.timed_out)
        self.assertLess(result.returncode, 0)

    def test_missing_tool_is_infrastructure_error(self):
        with self.assertRaisesRegex(RuntimeError, "cannot execute"):
            build.execute(["/no/such/compiler"])

    def test_sdk_environments_are_separate(self):
        with patch.dict(
            os.environ, {"LD_LIBRARY_PATH": "/wrong/sdk", "PYTHONPATH": "/wrong/python"}
        ):
            env = build.environment(build.STABLE)
        self.assertNotIn("/wrong", env["LD_LIBRARY_PATH"])
        self.assertNotIn("PYTHONPATH", env)
        self.assertEqual(env["MODULAR_HOME"], str(build.STABLE / "share/max"))


if __name__ == "__main__":
    unittest.main()

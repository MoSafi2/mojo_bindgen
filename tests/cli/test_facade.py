"""Presentation and subprocess-boundary contracts, without Python generation code."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

import mojo_bindgen
from mojo_bindgen import _process
from mojo_bindgen.cli import app

FAKE = """#!/usr/bin/env python3
import json,os,sys,signal
from pathlib import Path
args=sys.argv[1:]
Path(os.environ['FAKE_REQUESTS']).write_text(json.dumps(args))
for arg in args:
 if arg.startswith('--diagnostics-output=') and os.environ.get('FAKE_WARNING'):
  Path(arg.split('=',1)[1]).write_text(json.dumps([{'stage':'frontend','severity':'warning','message':'literal [red] warning λ','file':'a.h','line':2,'col':3,'decl_id':None}]))
if os.environ.get('FAKE_SIGNAL'): os.kill(os.getpid(),signal.SIGTERM)
sys.stdout.write(os.environ.get('FAKE_STDOUT','# bindings [red] λ\\n'))
sys.stderr.write(os.environ.get('FAKE_STDERR',''))
sys.exit(int(os.environ.get('FAKE_CODE','0')))
"""


class FacadeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="facade λ ")
        self.root = Path(self.directory.name)
        self.command = self.root / "bin/mojo-bindgen"
        self.command.parent.mkdir()
        self.command.write_text(FAKE)
        self.command.chmod(0o755)
        self.requests = self.root / "requests.json"
        self.environment = patch.dict(
            os.environ,
            {
                "MOJO_BINDGEN_EXECUTABLE": str(self.command),
                "FAKE_REQUESTS": str(self.requests),
            },
        )
        self.environment.start()
        self.runner = CliRunner()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_help_version_and_completion_do_not_start_generation(self):
        for args in (["--help"], ["--version"], ["--show-completion", "bash"]):
            with self.subTest(args=args):
                result = self.runner.invoke(app, args)
                self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(self.requests.exists())
        self.assertIn("mojo-bindgen", self.runner.invoke(app, ["--help"]).output)
        self.assertIn("0.4.0", self.runner.invoke(app, ["--version"]).output)

    def test_arguments_are_forwarded_without_shell_interpretation(self):
        header = self.root / "input ; λ.h"
        result = self.runner.invoke(
            app,
            [
                str(header),
                "--public-header",
                "sibling header.h",
                "-I",
                "include λ",
                "-D",
                "X=a b",
                "-U",
                "OLD",
                "--clang-arg=-funsigned-char",
                "--target",
                "i386-linux-gnu",
                "--link-mode",
                "owned-dl-handle",
                "--library-path",
                "/path with spaces/libλ.so",
                "--layout-tests",
                "layout.mojo",
                "--dump-cir",
                "cir.json",
                "--dump-mojo-ir",
                "mojo.json",
                "--no-doc-comments",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        args = json.loads(self.requests.read_text())
        for arg in (
            str(header),
            "--public-header=sibling header.h",
            "--include=include λ",
            "--define=X=a b",
            "--undefine=OLD",
            "--clang-arg=-funsigned-char",
            "--target=i386-linux-gnu",
            "--library-path=/path with spaces/libλ.so",
            "--layout-tests=layout.mojo",
            "--dump-cir=cir.json",
            "--no-doc-comments",
        ):
            self.assertIn(arg, args)
        self.assertEqual(result.stdout, "# bindings [red] λ\n")
        self.assertNotIn("\x1b", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_json_diagnostics_are_valid_uncolored_and_keep_literal_markup(self):
        result = self.runner.invoke(
            app, ["input.h", "--diagnostics", "json"], env={"FAKE_WARNING": "1"}
        )
        self.assertEqual(result.exit_code, 0, result.output)
        diagnostic = json.loads(result.stderr)[0]
        self.assertEqual(diagnostic["message"], "literal [red] warning λ")
        self.assertNotIn("\x1b", result.stderr)

    def test_text_diagnostics_honor_tty_color_and_no_color(self):
        for disabled in (False, True):
            env = {
                "FAKE_WARNING": "1",
                "FORCE_COLOR": "1",
                "NO_COLOR": None,
                "TERM": "xterm-256color",
            }
            if disabled:
                env["NO_COLOR"] = "1"
            result = self.runner.invoke(app, ["input.h"], color=True, env=env)
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("literal [red] warning λ", result.stderr)
            self.assertEqual("\x1b[" in result.stderr, not disabled)
            self.assertNotIn("\x1b", result.stdout)

    def test_diagnostic_file_and_silent_mode(self):
        target = self.root / "diagnostics.json"
        result = self.runner.invoke(
            app,
            ["input.h", "--diagnostics", "json", "--diagnostics-output", str(target)],
            env={"FAKE_WARNING": "1"},
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(target.read_text())[0]["severity"], "warning")
        self.assertEqual(result.stderr, "")
        result = self.runner.invoke(
            app, ["input.h", "--diagnostics", "silent"], env={"FAKE_WARNING": "1"}
        )
        self.assertEqual(result.stderr, "")

    def test_native_failure_and_warning_exit_keep_stdout_and_status(self):
        for code in (1, 2):
            result = self.runner.invoke(
                app,
                ["input.h", "--warnings-as-errors"],
                env={"FAKE_CODE": str(code), "FAKE_STDERR": "native failure\n"},
            )
            self.assertEqual(result.exit_code, code)
            self.assertIn("native failure", result.stderr)
            self.assertEqual(result.stdout, "# bindings [red] λ\n")
        self.assertIn("--warnings-as-errors", json.loads(self.requests.read_text()))

    def test_native_signal_is_a_nonzero_shell_status(self):
        result = self.runner.invoke(app, ["input.h"], env={"FAKE_SIGNAL": "1"})
        self.assertEqual(result.exit_code, 143)

    def test_missing_executable_has_actionable_error(self):
        result = self.runner.invoke(
            app, ["input.h"], env={"MOJO_BINDGEN_EXECUTABLE": str(self.root / "missing")}
        )
        self.assertEqual(result.exit_code, 127)
        self.assertIn("Reinstall", result.stderr)

    def test_public_mojo_path_and_python_surface(self):
        directory = self.root / "mojo"
        directory.mkdir()
        (directory / "mojo_bindgen.mojoc").touch()
        result = self.runner.invoke(app, ["--print-mojo-path"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.stdout.strip(), str(directory))
        self.assertFalse(hasattr(mojo_bindgen, "bindgen"))
        self.assertFalse(hasattr(mojo_bindgen, "BindgenOptions"))

    def test_interrupt_reaps_the_process_group(self):
        process = unittest.mock.Mock()
        process.pid = 999999999
        process.communicate.side_effect = [KeyboardInterrupt, ("", "")]
        with (
            patch.object(_process.subprocess, "Popen", return_value=process),
            patch.object(_process.os, "killpg") as kill,
        ):
            with self.assertRaises(KeyboardInterrupt):
                _process.invoke(["input.h"])
        kill.assert_called_once_with(process.pid, _process.signal.SIGTERM)
        self.assertEqual(process.communicate.call_count, 2)


if __name__ == "__main__":
    unittest.main()

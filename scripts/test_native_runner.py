"""Run the coordinator's standard-library-only self checks."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_testing import test_runner

unittest.main(module=test_runner)

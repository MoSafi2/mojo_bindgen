"""Fixed subsystem suite; individual files remain independently runnable."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case


from examples.test_examples import test_zlib_external_call
from examples.test_examples import test_zlib_owned_dl_handle
from examples.test_examples import test_cairo_external_call
from examples.test_examples import test_cairo_owned_dl_handle
from examples.test_examples import test_libpng_external_call
from examples.test_examples import test_libpng_owned_dl_handle
from examples.test_examples import test_sqlite_external_call
from examples.test_examples import test_sqlite_owned_dl_handle


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    var suite = TestSuite()
    suite.test[test_zlib_external_call]()
    suite.test[test_zlib_owned_dl_handle]()
    suite.test[test_cairo_external_call]()
    suite.test[test_cairo_owned_dl_handle]()
    suite.test[test_libpng_external_call]()
    suite.test[test_libpng_owned_dl_handle]()
    suite.test[test_sqlite_external_call]()
    suite.test[test_sqlite_owned_dl_handle]()
    suite^.run()

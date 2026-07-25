#!/usr/bin/env python3
"""Run the test suite.

    python3 run_tests.py         run everything
    python3 run_tests.py -v      verbose

Equivalent to `python3 -m unittest discover -s tests -t tests`, but without
having to remember the flags. Standard library only, no pytest needed.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent / "tests"


def main() -> int:
    # The tests import `helpers`, which lives alongside them.
    sys.path.insert(0, str(TESTS_DIR))

    verbosity = 2 if any(a in ("-v", "--verbose") for a in sys.argv[1:]) else 1
    suite = unittest.defaultTestLoader.discover(str(TESTS_DIR), top_level_dir=str(TESTS_DIR))
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

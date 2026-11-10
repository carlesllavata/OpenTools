"""Runs the offline tests (no 3ds Max needed).

    "C:\\Program Files\\Autodesk\\3ds Max 2027\\Python\\python.exe" -I dev/run_tests.py
"""

import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True  # keep __pycache__ off the network share
sys.path.insert(0, os.path.join(REPO, "OpenTools.bundle", "Contents", "python"))


def main():
    tests_dir = os.path.join(REPO, "tests")
    suite = unittest.defaultTestLoader.discover(tests_dir, top_level_dir=tests_dir)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

"""Tests for the HOME fallback (item 2.6)."""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utilities  # noqa: E402


class GetHomeDirTest(unittest.TestCase):
    def test_uses_expanduser_when_home_is_set(self):
        with mock.patch.dict(os.environ, {"HOME": "/home/tester"}, clear=True):
            self.assertEqual(utilities.get_home_dir(), "/home/tester")

    def test_falls_back_to_tempdir_when_expanduser_cannot_resolve(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("os.path.expanduser", return_value="~"):
                self.assertEqual(utilities.get_home_dir(), tempfile.gettempdir())

    def test_does_not_raise_without_home(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(utilities.get_home_dir(), str)


if __name__ == "__main__":
    unittest.main()

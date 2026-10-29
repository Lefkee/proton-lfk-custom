"""Tests for path containment (item 2.4)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utilities  # noqa: E402


class IsPathWithinTest(unittest.TestCase):
    def test_sibling_prefix_is_not_within(self):
        # The old substring check matched this: '/games' in '/games2/x'.
        self.assertFalse(utilities.is_path_within("/games2/x", "/games"))
        self.assertFalse(utilities.is_path_within("/games3", "/games"))

    def test_child_is_within(self):
        self.assertTrue(utilities.is_path_within("/games/x", "/games"))
        self.assertTrue(utilities.is_path_within("/games/steamapps/common/x", "/games"))

    def test_same_path_is_within(self):
        self.assertTrue(utilities.is_path_within("/games", "/games"))

    def test_parent_is_not_within_child(self):
        self.assertFalse(utilities.is_path_within("/games", "/games/x"))

    def test_trailing_slash_is_normalised(self):
        self.assertTrue(utilities.is_path_within("/games/x", "/games/"))

    def test_nonexistent_paths_still_work(self):
        # realpath does not require the paths to exist.
        self.assertTrue(utilities.is_path_within("/nonexistent/a/b", "/nonexistent/a"))
        self.assertFalse(utilities.is_path_within("/nonexistent/ab", "/nonexistent/a"))

    def test_mixed_relative_absolute_is_false(self):
        self.assertFalse(utilities.is_path_within("relative/path", "/absolute"))


if __name__ == "__main__":
    unittest.main()

"""Tests for prefix version parsing (item 1.2)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prefix_version import parse_prefix_version  # noqa: E402


class ParsePrefixVersionTest(unittest.TestCase):
    def test_ge_versions_order_correctly(self):
        old = parse_prefix_version("GE-Proton10-9")
        new = parse_prefix_version("GE-Proton11-11")
        self.assertIsNotNone(old)
        self.assertIsNotNone(new)
        # (major, minor) is what upgrade_pfx compares.
        self.assertLess(old[1:3], new[1:3])

    def test_ge_same_base_build_order(self):
        older = parse_prefix_version("GE-Proton11-10")
        newer = parse_prefix_version("GE-Proton11-11")
        self.assertLess(older[1:3], newer[1:3])

    def test_ge_fields(self):
        self.assertEqual(
            parse_prefix_version("GE-Proton10-9"),
            ("GE-Proton10", 10, 9, "9"),
        )

    def test_ge_newer_detection(self):
        # A prefix built by a newer GE release must be treated as newer.
        old = parse_prefix_version("GE-Proton12-1")
        new = parse_prefix_version("GE-Proton11-11")
        self.assertGreater(old[1:3], new[1:3])

    def test_valve_63(self):
        parsed = parse_prefix_version("6.3-3")
        self.assertEqual(parsed, ("6.3", 6, 3, "3"))
        # Code under test compares these as ints.
        self.assertLess(int(parsed[1]), 6 + 1)

    def test_valve_37(self):
        parsed = parse_prefix_version("3.7-1")
        self.assertEqual(parsed, ("3.7", 3, 7, "1"))
        self.assertEqual(parsed[0], "3.7")

    def test_garbage(self):
        self.assertIsNone(parse_prefix_version("garbage"))

    def test_empty(self):
        self.assertIsNone(parse_prefix_version(""))
        self.assertIsNone(parse_prefix_version(None))

    def test_whitespace_is_tolerated(self):
        self.assertEqual(parse_prefix_version(" GE-Proton11-11\n")[1:3], (11, 11))

    def test_current_prefix_version_in_proton_parses(self):
        """CURRENT_PREFIX_VERSION in the launcher must be parseable."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "proton"), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("CURRENT_PREFIX_VERSION"):
                    _, value = line.split("=", 1)
                    self.assertIsNotNone(parse_prefix_version(value.strip().strip('"')))
                    return
        self.fail("CURRENT_PREFIX_VERSION not found in proton")


if __name__ == "__main__":
    unittest.main()

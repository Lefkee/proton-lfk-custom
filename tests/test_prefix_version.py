"""Tests for prefix version parsing (item 1.2)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prefix_version import is_newer_prefix, parse_prefix_version  # noqa: E402


class ParsePrefixVersionTest(unittest.TestCase):
    def test_ge_versions_order_correctly(self):
        old = parse_prefix_version("GE-Proton10-9")
        new = parse_prefix_version("GE-Proton11-11")
        self.assertIsNotNone(old)
        self.assertIsNotNone(new)
        # Only the Wine base is comparable for GE releases.
        self.assertLess(old[1:3], new[1:3])

    def test_ge_build_number_does_not_order(self):
        older = parse_prefix_version("GE-Proton11-10")
        newer = parse_prefix_version("GE-Proton11-11")
        self.assertEqual(older[1:3], newer[1:3])

    def test_ge_fields(self):
        self.assertEqual(
            parse_prefix_version("GE-Proton10-9"),
            ("GE-Proton10", 10, 0, "9"),
        )

    def test_ge_newer_detection(self):
        # A prefix built on a newer Wine base must be treated as newer.
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
        self.assertEqual(parse_prefix_version(" GE-Proton11-11\n"), ("GE-Proton11", 11, 0, "11"))

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


class IsNewerPrefixTest(unittest.TestCase):
    def parse(self, version):
        parsed = parse_prefix_version(version)
        self.assertIsNotNone(parsed, version)
        return parsed

    def test_ge_higher_build_is_not_newer(self):
        # GE-Proton11-12 -> GE-Proton11-11 is not a downgrade: build numbers
        # must not trigger the "Removing newer prefix" cleanup.
        self.assertFalse(
            is_newer_prefix(self.parse("GE-Proton11-12"), self.parse("GE-Proton11-11"))
        )

    def test_ge_higher_base_is_newer(self):
        self.assertTrue(
            is_newer_prefix(self.parse("GE-Proton12-1"), self.parse("GE-Proton11-11"))
        )

    def test_ge_same_version_is_not_newer(self):
        self.assertFalse(
            is_newer_prefix(self.parse("GE-Proton11-11"), self.parse("GE-Proton11-11"))
        )

    def test_valve_minor_still_compared(self):
        self.assertTrue(is_newer_prefix(self.parse("9.0-4"), self.parse("6.3-3")))
        self.assertFalse(is_newer_prefix(self.parse("6.3-3"), self.parse("6.3-3")))
        self.assertTrue(is_newer_prefix(self.parse("6.4-1"), self.parse("6.3-3")))

    def test_unparsed_returns_none(self):
        self.assertIsNone(is_newer_prefix(None, self.parse("GE-Proton11-11")))
        self.assertIsNone(is_newer_prefix(self.parse("GE-Proton11-11"), None))


if __name__ == "__main__":
    unittest.main()

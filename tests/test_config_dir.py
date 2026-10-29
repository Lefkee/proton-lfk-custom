"""Tests for the protonfixes config directory (item 2.2)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utilities  # noqa: E402


class MigrateLegacyConfigDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.old = self.tmp / "cache" / "protonfixes"
        self.new = self.tmp / "config" / "protonfixes"
        self.old.mkdir(parents=True)
        self.log = mock.Mock()

    def tearDown(self):
        self._tmp.cleanup()

    def test_copies_regular_files_and_keeps_old_ones(self):
        (self.old / "config.ini").write_text("[main]\n", encoding="utf-8")
        (self.old / "localfixes").mkdir()
        (self.old / "localfixes" / "fix.py").write_text("# fix\n", encoding="utf-8")

        with mock.patch.object(utilities, "log", self.log):
            copied = utilities.migrate_legacy_config_dir(self.old, self.new)

        self.assertEqual(copied, ["config.ini"])
        self.assertEqual((self.new / "config.ini").read_text(encoding="utf-8"), "[main]\n")
        self.assertTrue((self.old / "config.ini").exists())
        # Cache subdirectories are not config and must not be copied.
        self.assertFalse((self.new / "localfixes").exists())
        self.log.info.assert_called_once()

    def test_is_idempotent(self):
        (self.old / "config.ini").write_text("a", encoding="utf-8")
        with mock.patch.object(utilities, "log", self.log):
            utilities.migrate_legacy_config_dir(self.old, self.new)
            copied = utilities.migrate_legacy_config_dir(self.old, self.new)
        self.assertEqual(copied, [])

    def test_no_old_dir_is_a_noop(self):
        missing = self.tmp / "nope"
        self.assertEqual(
            utilities.migrate_legacy_config_dir(missing, self.new), []
        )
        self.assertFalse(self.new.exists())

    def test_existing_destination_is_not_overwritten(self):
        (self.old / "config.ini").write_text("old", encoding="utf-8")
        self.new.mkdir(parents=True)
        (self.new / "config.ini").write_text("new", encoding="utf-8")
        self.assertEqual(
            utilities.migrate_legacy_config_dir(self.old, self.new), []
        )
        self.assertEqual((self.new / "config.ini").read_text(encoding="utf-8"), "new")

    def test_config_dir_property_uses_config_home_and_migrates(self):
        (self.old / "config.ini").write_text("x", encoding="utf-8")
        with mock.patch.object(utilities, "base_config", self.tmp / "config"), \
                mock.patch.object(utilities, "base_cache", self.tmp / "cache"), \
                mock.patch.object(utilities, "log", self.log):
            directory = utilities.config.path.config_dir

        self.assertEqual(directory, self.tmp / "config" / "protonfixes")
        self.assertTrue((directory / "config.ini").is_file())

    def test_config_dir_is_under_xdg_config_home(self):
        with mock.patch.object(utilities, "base_config", self.tmp / "config"), \
                mock.patch.object(utilities, "base_cache", self.tmp / "cache"), \
                mock.patch.object(utilities, "log", self.log):
            directory = utilities.config.path.config_dir
        self.assertEqual(directory.name, "protonfixes")
        self.assertEqual(directory.parent.name, "config")


if __name__ == "__main__":
    unittest.main()

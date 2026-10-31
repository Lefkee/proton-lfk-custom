"""Tests for the patch-script git helpers (item 1.4c)."""

import os
import shlex
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_SH = os.path.join(ROOT, "patches", "lib.sh")


class GitHelpersTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        )

    def write(self, relpath, content):
        path = os.path.join(self.repo, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def read(self, relpath):
        with open(os.path.join(self.repo, relpath), encoding="utf-8") as handle:
            return handle.read()

    def run_helper(self, body):
        script = os.path.join(self.tmp, "run.sh")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/bash\n"
                f"source {shlex.quote(LIB_SH)}\n"
                f"{body}\n"
            )
        return subprocess.run(
            ["bash", script],
            cwd=self.repo,
            capture_output=True,
            text=True,
        )

    def test_enter_clean_subdir_does_not_reset_parent(self):
        # 'sub' is a plain directory tracked by the parent repository, like
        # wineopenxr. It is not its own repository root.
        self.write("tracked.txt", "original\n")
        self.write("sub/tracked.txt", "sub original\n")
        self.git("add", "tracked.txt", "sub/tracked.txt")
        self.git("commit", "-qm", "init")

        # A local modification outside 'sub' must survive; reset --hard would
        # discard it. Inside 'sub', checkout restores tracked files and clean
        # removes untracked ones, scoped to that directory.
        self.write("tracked.txt", "modified\n")
        self.write("sub/tracked.txt", "sub modified\n")
        self.write("sub/untracked.txt", "junk\n")

        result = self.run_helper("enter_clean_subdir sub\nleave_dir\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read("tracked.txt"), "modified\n")
        self.assertEqual(self.read("sub/tracked.txt"), "sub original\n")
        self.assertFalse(
            os.path.exists(os.path.join(self.repo, "sub", "untracked.txt"))
        )

    def test_enter_clean_dir_still_rejects_plain_subdir(self):
        self.write("tracked.txt", "original\n")
        self.git("add", "tracked.txt")
        self.git("commit", "-qm", "init")
        os.makedirs(os.path.join(self.repo, "sub"))
        self.write("tracked.txt", "modified\n")

        result = self.run_helper("enter_clean_dir sub\nleave_dir\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not its own root", result.stderr)
        # It must abort before reset --hard can touch the parent.
        self.assertEqual(self.read("tracked.txt"), "modified\n")


if __name__ == "__main__":
    unittest.main()

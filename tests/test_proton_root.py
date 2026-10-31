"""Tests for Proton's root resolution and argv handling (item 2.5)."""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTON = os.path.join(ROOT, "proton")

sys.path.insert(0, ROOT)


def load_proton_module():
    loader = importlib.machinery.SourceFileLoader("proton_under_test", PROTON)
    spec = importlib.util.spec_from_loader("proton_under_test", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ProtonRootTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proton = load_proton_module()

    def test_root_follows_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            real_dir = os.path.join(tmp, "real")
            os.makedirs(real_dir)
            real_script = os.path.join(real_dir, "proton")
            with open(real_script, "w", encoding="utf-8"):
                pass
            link = os.path.join(tmp, "proton-link")
            os.symlink(real_script, link)

            original = self.proton.__file__
            try:
                self.proton.__file__ = link
                self.assertEqual(self.proton.proton_root(), real_dir)
            finally:
                self.proton.__file__ = original


class ProtonArgvTest(unittest.TestCase):
    def run_proton(self, *args):
        env = os.environ.copy()
        env.pop("STEAM_COMPAT_DATA_PATH", None)
        return subprocess.run(
            [sys.executable, PROTON, *args],
            env=env,
            capture_output=True,
            text=True,
        )

    def test_no_arguments_prints_usage_and_exits_2(self):
        result = self.run_proton()
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage: proton <verb>", result.stderr)

    def test_help_exits_0(self):
        result = self.run_proton("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage: proton <verb>", result.stdout)


if __name__ == "__main__":
    unittest.main()

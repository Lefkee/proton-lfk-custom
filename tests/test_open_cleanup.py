"""Regression tests for the open() cleanup in item 2.6."""

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTON = os.path.join(ROOT, "proton")

sys.path.insert(0, ROOT)

import default_pfx  # noqa: E402


def load_proton_module():
    loader = importlib.machinery.SourceFileLoader("proton_registry_under_test", PROTON)
    spec = importlib.util.spec_from_loader("proton_registry_under_test", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ReplaceRegValueTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proton = load_proton_module()

    def test_replaces_value_and_returns_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "system.reg")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    '[Software\\\\Microsoft\\\\Cryptography] 1234\n'
                    '"MachineGuid"="old-guid"\n'
                    '"Other"="keep"\n'
                )

            old = self.proton.get_replace_reg_value(
                path,
                "Software\\\\Microsoft\\\\Cryptography",
                "MachineGuid",
                '"new-guid"',
            )

            self.assertEqual(old, '"old-guid"\n')
            with open(path, encoding="utf-8") as handle:
                contents = handle.read()
            self.assertIn('"MachineGuid"="new-guid"\n', contents)
            self.assertIn('"Other"="keep"\n', contents)
            self.assertFalse(os.path.exists(path + ".new"))

    def test_lookup_does_not_modify_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "system.reg")
            original = (
                '[Software\\\\Microsoft\\\\Cryptography] 1234\n'
                '"MachineGuid"="old-guid"\n'
            )
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(original)

            old = self.proton.get_replace_reg_value(
                path,
                "Software\\\\Microsoft\\\\Cryptography",
                "MachineGuid",
            )

            self.assertEqual(old, '"old-guid"\n')
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), original)


class DefaultPfxFileTest(unittest.TestCase):
    def test_wine_builtin_dll_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "builtin.dll")
            with open(path, "wb") as handle:
                handle.write(b"\0" * 0x40)
                handle.write(b"Wine builtin DLL")
            self.assertTrue(default_pfx.file_is_wine_builtin_dll(path))

            with open(path, "wb") as handle:
                handle.write(b"\0" * 0x40)
                handle.write(b"not a wine dll")
            self.assertFalse(default_pfx.file_is_wine_builtin_dll(path))

    def test_dll_bitness(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pe.dll")
            for magic, expected in ((b"\x0b\x01", 32), (b"\x0b\x02", 64), (b"\x0b\x03", 0)):
                with open(path, "wb") as handle:
                    handle.write(b"\0" * 0x3c)
                    handle.write((0x40).to_bytes(4, "little"))
                    handle.seek(0x18 + 0x40)
                    handle.write(magic)
                self.assertEqual(default_pfx.dll_bitness(path), expected)


if __name__ == "__main__":
    unittest.main()

"""Tests for lazy libvulkan loading (item 1.3)."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utilities  # noqa: E402
import vulkan  # noqa: E402


class LazyVulkanTest(unittest.TestCase):
    def setUp(self):
        vulkan._libvulkan = None
        vulkan.vkCreateInstance = None
        utilities.get_vulkan_gpus.cache_clear()

    def tearDown(self):
        vulkan._libvulkan = None
        vulkan.vkCreateInstance = None
        utilities.get_vulkan_gpus.cache_clear()

    def test_import_does_not_load_libvulkan(self):
        self.assertIsNone(vulkan._libvulkan)

    def test_missing_libvulkan_raises_vulkan_error(self):
        with mock.patch.object(vulkan, "CDLL", side_effect=OSError("not found")):
            with self.assertRaises(vulkan.VulkanError) as ctx:
                vulkan._get_libvulkan()
        self.assertIn("libvulkan.so.1", str(ctx.exception))

    def test_get_vulkan_gpus_returns_empty_when_loader_missing(self):
        with mock.patch.object(vulkan, "CDLL", side_effect=OSError("not found")):
            self.assertEqual(utilities.get_vulkan_gpus(), [])


if __name__ == "__main__":
    unittest.main()

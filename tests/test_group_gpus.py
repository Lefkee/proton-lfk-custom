"""Tests for GPU grouping (item 2.3)."""

import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utilities  # noqa: E402
from vulkan import VkPhysicalDeviceType  # noqa: E402


def fake_gpu(device_type, name, uuid):
    return SimpleNamespace(deviceType=device_type, deviceName=name, deviceUUID=uuid)


class GroupGpusTest(unittest.TestCase):
    def test_interleaved_types_do_not_overwrite(self):
        dgpu1 = fake_gpu(VkPhysicalDeviceType.DISCRETE_GPU, "dGPU 1", "11111111-1111-1111-1111-111111111111")
        igpu = fake_gpu(VkPhysicalDeviceType.INTEGRATED_GPU, "iGPU", "22222222-2222-2222-2222-222222222222")
        dgpu2 = fake_gpu(VkPhysicalDeviceType.DISCRETE_GPU, "dGPU 2", "33333333-3333-3333-3333-333333333333")

        grouped = utilities.group_gpus([dgpu1, igpu, dgpu2])

        self.assertEqual(grouped[VkPhysicalDeviceType.DISCRETE_GPU], [dgpu1, dgpu2])
        self.assertEqual(grouped[VkPhysicalDeviceType.INTEGRATED_GPU], [igpu])

    def test_filter_matches_name_and_dashed_uuid(self):
        dgpu = fake_gpu(VkPhysicalDeviceType.DISCRETE_GPU, "RX 7900 XTX", "abcd-1234")
        other = fake_gpu(VkPhysicalDeviceType.DISCRETE_GPU, "GTX 1080", "ffff-9999")

        by_name = utilities.group_gpus([dgpu, other], "RX 7900")
        self.assertEqual(by_name[VkPhysicalDeviceType.DISCRETE_GPU], [dgpu])

        by_uuid = utilities.group_gpus([dgpu, other], "abcd1234")
        self.assertEqual(by_uuid[VkPhysicalDeviceType.DISCRETE_GPU], [dgpu])

    def test_no_filter_keeps_everything(self):
        gpus = [
            fake_gpu(VkPhysicalDeviceType.INTEGRATED_GPU, "a", "1"),
            fake_gpu(VkPhysicalDeviceType.VIRTUAL_GPU, "b", "2"),
            fake_gpu(VkPhysicalDeviceType.CPU, "c", "3"),
        ]
        grouped = utilities.group_gpus(gpus)
        self.assertEqual(sum(len(items) for items in grouped.values()), 3)

    def test_empty_list(self):
        self.assertEqual(dict(utilities.group_gpus([])), {})


if __name__ == "__main__":
    unittest.main()

import unittest
from app.launch import inference_arguments

class GpuConfigurationTests(unittest.TestCase):
    def test_gpu_memory_budget_is_validated(self):
        for value in (0, -1, 1, True, "0.8", float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                inference_arguments({"gpu_memory_utilization":value})
        self.assertEqual(inference_arguments({"gpu_memory_utilization":0.82}), ["--gpu-memory-utilization", "0.82"])

    def test_explicit_kv_cache_budget_is_positive_integer(self):
        for value in (0, True, 1.2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                inference_arguments({"kv_cache_memory_bytes":value})
        self.assertEqual(inference_arguments({"kv_cache_memory_bytes":536870912}), ["--kv-cache-memory-bytes", "536870912"])

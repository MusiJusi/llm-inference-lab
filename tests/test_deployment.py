import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class DeploymentTests(unittest.TestCase):
    def test_compose_and_kubernetes_share_model_and_inference_configuration(self):
        for name in ("model.env", "inference.json"):
            self.assertEqual((ROOT / "config" / name).read_text(), (ROOT / "k8s/base/config" / name).read_text())

    def test_local_deployment_uses_separate_names_and_explicit_gpu(self):
        compose = (ROOT / "compose.yaml").read_text()
        self.assertIn("name: llm-inference-lab", compose)
        self.assertIn("gpus: all", compose)
        self.assertIn("127.0.0.1:8001:8000", compose)
        self.assertNotIn("kaspersky", compose.lower())
        self.assertIn('nvidia.com/gpu: "1"', (ROOT / "k8s/base/deployment.yaml").read_text())

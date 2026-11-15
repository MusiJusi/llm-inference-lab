"""Record the actual GPU backend, selected model and reproducible runtime metadata."""

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.runtime import (
    CONTAINER, PROFILES, compose_command, compose_configuration,
    inference_settings, validate_running_model,
)

PROBE = """
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import torch
from app.model_store import model_location

snapshot_path = model_location(Path(os.environ.get("MODEL_ROOT", "/models")), os.environ["MODEL_ID"], os.environ["MODEL_REVISION"])
manifest = json.loads((snapshot_path / ".complete.json").read_text())
weights = [entry for name, entry in manifest["files"].items() if name.endswith(".safetensors")]

assert os.getuid() == 10001
assert torch.cuda.is_available()
assert float((torch.ones(4, device='cuda') * 2).sum()) == 8
print(json.dumps({
    'uid': os.getuid(),
    'vllm': importlib.metadata.version('vllm'),
    'torch': torch.__version__,
    'python': platform.python_version(),
    'cuda': torch.version.cuda,
    'gpu': torch.cuda.get_device_name(0),
    'compute_capability': torch.cuda.get_device_capability(0),
    'gpu_memory_bytes': torch.cuda.get_device_properties(0).total_memory,
    'cuda_computation': 'passed',
    'inference': json.loads(Path('/config/inference.json').read_text()),
    'snapshot': {'weight_bytes': sum(entry['size'] for entry in weights), 'weight_shards': len(weights)},
}))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="default")
    parser.add_argument("--output", type=Path, default=ROOT / "results/environment.json")
    args = parser.parse_args()
    configuration = compose_configuration(args.profile)
    details = json.loads(subprocess.check_output(["docker", "inspect", CONTAINER], text=True))[0]
    model = validate_running_model(configuration, details)
    result = subprocess.run(
        compose_command(args.profile) + ["exec", "-T", "server", "python3", "-c", PROBE],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    runtime = json.loads(result.stdout.splitlines()[-1])
    settings = runtime.pop("inference")
    snapshot = runtime.pop("snapshot")
    if settings != inference_settings(configuration):
        raise RuntimeError("The running inference configuration differs from the selected profile.")
    image = json.loads((ROOT / "config/runtime.json").read_text(encoding="utf-8"))["base_image"]
    base = json.loads(subprocess.check_output(["docker", "image", "inspect", image], text=True))[0]
    report = {
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "profile": args.profile,
        "runtime": runtime,
        "image_id": details["Image"],
        "base_image_digests": base.get("RepoDigests", []),
        "inference": settings,
        "snapshot": snapshot,
        "model": model,
        "deployment": "Docker Compose, Windows / WSL 2, one NVIDIA GPU",
        "limits": {
            "cpus": details["HostConfig"]["NanoCpus"] / 10**9,
            "memory_gib": details["HostConfig"]["Memory"] / 2**30,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(runtime, indent=2))


if __name__ == "__main__":
    main()

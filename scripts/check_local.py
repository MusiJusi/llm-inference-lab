"""Validate the selected Compose endpoint, private logs, offline cache and restart."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.runtime import (
    CONTAINER, PROFILES, cache_mount_argument, compose_command,
    compose_configuration, inference_settings, validate_running_model,
)


def run(*command, capture=False):
    return subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=capture)


def wait_ready(base_url, timeout=900):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(base_url + "/health", timeout=3) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, ConnectionError):
            pass
        status = json.loads(run("docker", "inspect", CONTAINER, capture=True).stdout)[0]["State"]
        if not status["Running"]:
            raise RuntimeError("The GPU server exited before readiness; inspect Compose logs.")
        time.sleep(2)
    raise TimeoutError("The GPU server did not become ready.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--profile", choices=PROFILES, default="default")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    wait_ready(args.base_url)
    configuration = compose_configuration(args.profile)
    details = json.loads(run("docker", "inspect", CONTAINER, capture=True).stdout)[0]
    model = validate_running_model(configuration, details)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    smoke = [sys.executable, "scripts/smoke_test.py", "--base-url", args.base_url,
             "--profile", args.profile]
    run(*smoke, "--output", str(args.output_dir / "smoke.json"))
    offline = run(
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--mount", cache_mount_argument(configuration),
        "--env", "MODEL_ID=" + model["MODEL_ID"],
        "--env", "MODEL_REVISION=" + model["MODEL_REVISION"],
        "--entrypoint", "python", "llm-inference-lab-downloader:dev", "-c",
        "import socket,sys; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network access forbidden')); sys.modules['huggingface_hub']=None; from app.download_model import main; raise SystemExit(main())",
        capture=True,
    )
    if '"model_cache_hit"' not in offline.stdout:
        raise RuntimeError("Offline model cache was not used.")
    before = json.loads(run("docker", "inspect", CONTAINER, capture=True).stdout)[0]
    run(*compose_command(args.profile), "restart", "server")
    wait_ready(args.base_url)
    after = json.loads(run("docker", "inspect", CONTAINER, capture=True).stdout)[0]
    if before["Image"] != after["Image"] or before["State"]["StartedAt"] == after["State"]["StartedAt"]:
        raise RuntimeError("The server did not restart with the same image.")
    run(*smoke, "--output", str(args.output_dir / "smoke-after-restart.json"))
    if args.benchmark:
        run(sys.executable, "scripts/benchmark.py", "--base-url", args.base_url,
            "--model", inference_settings(configuration)["served_model_name"],
            "--output", str(args.output_dir / "benchmark.json"))
    report = {
        "endpoint": "passed", "authentication": "passed", "streaming": "passed",
        "log_privacy": "passed", "network_forbidden_cache": "passed",
        "restart_same_image": "passed", "post_restart_endpoint": "passed",
        "profile": args.profile, "model": model["MODEL_ID"],
    }
    (args.output_dir / "integration.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Compose GPU integration checks passed.")


if __name__ == "__main__":
    main()

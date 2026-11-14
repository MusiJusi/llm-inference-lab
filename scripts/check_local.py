"""Validate the Compose endpoint, private logs, offline cache and process restart."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

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
        status = json.loads(run("docker", "inspect", "llm-inference-lab-server-1", capture=True).stdout)[0]["State"]
        if not status["Running"]:
            raise RuntimeError("The GPU server exited before readiness; inspect docker compose logs server.")
        time.sleep(2)
    raise TimeoutError("The GPU server did not become ready.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()
    wait_ready(args.base_url)
    smoke = [sys.executable, "scripts/smoke_test.py", "--base-url", args.base_url]
    run(*smoke, "--output", "results/smoke.json")
    config = dict(line.split("=", 1) for line in (ROOT / "config/model.env").read_text().splitlines() if line and not line.startswith("#"))
    offline = run("docker", "run", "--rm", "--network", "none", "--read-only",
        "--mount", "type=volume,src=llm-inference-lab-models,dst=/models",
        "--env", "MODEL_ID="+config["MODEL_ID"], "--env", "MODEL_REVISION="+config["MODEL_REVISION"],
        "--entrypoint", "python", "llm-inference-lab-downloader:dev", "-c",
        "import socket,sys; socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network access forbidden')); sys.modules['huggingface_hub']=None; from app.download_model import main; raise SystemExit(main())", capture=True)
    if '"model_cache_hit"' not in offline.stdout:
        raise RuntimeError("Offline model cache was not used.")
    before = json.loads(run("docker", "inspect", "llm-inference-lab-server-1", capture=True).stdout)[0]
    run("docker", "compose", "restart", "server")
    wait_ready(args.base_url)
    after = json.loads(run("docker", "inspect", "llm-inference-lab-server-1", capture=True).stdout)[0]
    if before["Image"] != after["Image"] or before["State"]["StartedAt"] == after["State"]["StartedAt"]:
        raise RuntimeError("The server did not restart with the same image.")
    run(*smoke, "--output", "results/smoke-after-restart.json")
    if args.benchmark:
        run(sys.executable, "scripts/benchmark.py", "--base-url", args.base_url)
    report = {"endpoint":"passed", "authentication":"passed", "streaming":"passed", "log_privacy":"passed", "network_forbidden_cache":"passed", "restart_same_image":"passed", "post_restart_endpoint":"passed"}
    output=ROOT / "results/integration.json"; output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n")
    print("Compose GPU integration checks passed.")

if __name__ == "__main__":
    main()

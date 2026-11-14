"""Verify the real Kubernetes endpoint, offline model cache, and Pod restart."""

import argparse
import contextlib
import copy
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def kubectl(context, *arguments, document=None):
    return subprocess.run(
        ["kubectl", "--context", context, "-n", "llm-inference-lab", *arguments],
        input=json.dumps(document) if document is not None else None,
        capture_output=True, text=True, check=True,
    ).stdout


@contextlib.contextmanager
def forwarded_api(context):
    (ROOT / ".local").mkdir(exist_ok=True)
    with (ROOT / ".local/port-forward.log").open("w") as log:
        process = subprocess.Popen(
            ["kubectl", "--context", context, "-n", "llm-inference-lab", "port-forward", "service/vllm", "8001:8000"],
            stdout=log, stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Port forwarding failed; check .local/port-forward.log.")
                try:
                    with urlopen("http://127.0.0.1:8001/health", timeout=2) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.5)
            else:
                raise RuntimeError("The forwarded API did not become ready.")
            yield
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def offline_cache_check(context, deployment):
    template = deployment["spec"]["template"]["spec"]
    downloader = copy.deepcopy(template["initContainers"][0])
    downloader["name"] = "cache-check"
    downloader["resources"] = {
        "requests": {"cpu": "10m", "memory": "64Mi"},
        "limits": {"cpu": "1", "memory": "256Mi"},
    }
    downloader["env"] = [
        {"name": "HF_HUB_OFFLINE", "value": "1"},
        {"name": "HF_ENDPOINT", "value": "http://127.0.0.1:9"},
    ]
    downloader["command"] = ["python", "-c", (
        "import socket,sys; "
        "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network access forbidden')); "
        "sys.modules['huggingface_hub']=None; "
        "from app.download_model import main; raise SystemExit(main())"
    )]
    name = "model-cache-check-" + uuid.uuid4().hex[:8]
    job = {
        "apiVersion": "batch/v1", "kind": "Job",
        "metadata": {"name": name},
        "spec": {"backoffLimit": 0, "ttlSecondsAfterFinished": 300, "template": {"spec": {
            "restartPolicy": "Never", "automountServiceAccountToken": False,
            "enableServiceLinks": False,
            "securityContext": template["securityContext"],
            "containers": [downloader],
            "volumes": [volume for volume in template["volumes"] if volume["name"] in {"models", "init-tmp"}],
        }}},
    }
    kubectl(context, "create", "-f", "-", document=job)
    try:
        kubectl(context, "wait", "--for=condition=complete", "job/" + name, "--timeout=120s")
        logs = kubectl(context, "logs", "job/" + name)
        if not any(json.loads(line).get("event") == "model_cache_hit" for line in logs.splitlines() if line.startswith("{")):
            raise RuntimeError("The offline Job did not use the completed local snapshot.")
    except subprocess.CalledProcessError as error:
        pods = json.loads(kubectl(context, "get", "pods", "-l", "job-name=" + name, "-o", "json"))
        reasons = [condition.get("message", condition.get("reason", "unknown"))
                   for pod in pods["items"]
                   for condition in pod.get("status", {}).get("conditions", [])
                   if condition.get("type") == "PodScheduled" and condition.get("status") == "False"]
        raise RuntimeError("The offline cache Job failed. " + " ".join(reasons)) from error
    finally:
        kubectl(context, "delete", "job", name, "--wait=false")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", default="llm-inference-lab-gpu")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "results/kubernetes.json")
    args = parser.parse_args()
    smoke = [sys.executable, str(ROOT / "scripts/smoke_test.py"), "--context", args.context, "--backend", "kubernetes"]
    deployment = json.loads(kubectl(args.context, "get", "deployment", "vllm", "-o", "json"))
    with forwarded_api(args.context):
        subprocess.run(smoke, check=True)
        if args.benchmark:
            subprocess.run([sys.executable, str(ROOT / "scripts/benchmark.py")], check=True)

    offline_cache_check(args.context, deployment)
    kubectl(args.context, "rollout", "restart", "deployment/vllm")
    kubectl(args.context, "rollout", "status", "deployment/vllm", "--timeout=30m")
    logs = kubectl(args.context, "logs", "deployment/vllm", "-c", "download-model")
    if '"model_cache_hit"' not in logs:
        raise RuntimeError("The restarted Pod did not use the local model cache.")
    with forwarded_api(args.context):
        subprocess.run(smoke, check=True)
    runtime_command = "import json,os,torch; assert os.getuid()==10001; assert torch.cuda.is_available(); assert float(torch.ones(4,device='cuda').sum())==4; print(json.dumps({'uid':os.getuid(),'gpu':torch.cuda.get_device_name(0),'cuda':torch.version.cuda,'cuda_computation':'passed'}))"
    runtime = json.loads(kubectl(args.context, "exec", "deployment/vllm", "-c", "server", "--", "python3", "-c", runtime_command).splitlines()[-1])
    (ROOT / "results").mkdir(exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "endpoint": "passed", "log_privacy": "passed", "offline_cache": "passed",
        "pod_restart": "passed", "post_restart_endpoint": "passed", "gpu_runtime": runtime,
    }, indent=2) + "\n", encoding="utf-8")
    print("Kubernetes integration checks passed.")


if __name__ == "__main__":
    main()

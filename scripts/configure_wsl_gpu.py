"""Expose the WSL DirectX bridge to the NVIDIA device plugin in this lab cluster."""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = "llm-inference-lab-gpu"

def main():
    environment = {**os.environ, "KUBECONFIG": str(ROOT / ".local/kubeconfig")}
    command = ["kubectl", "--context", CONTEXT]
    def kubectl(*args, document=None):
        return subprocess.run(command + list(args), input=None if document is None else json.dumps(document), env=environment, text=True, capture_output=True, check=True).stdout
    nodes = json.loads(kubectl("get", "nodes", "-o", "json"))["items"]
    if len(nodes) != 1 or nodes[0]["metadata"]["name"] != CONTEXT:
        raise RuntimeError("This helper supports only the dedicated single-node inference-lab cluster.")
    generated = subprocess.run(["docker","exec",CONTEXT,"nvidia-ctk","cdi","generate","--mode=wsl","--format=json"],capture_output=True,text=True,check=True)
    spec = json.loads(generated.stdout)
    mounts = spec.setdefault("containerEdits",{}).setdefault("mounts",[])
    if not any(item.get("containerPath") == "/usr/lib/x86_64-linux-gnu/libdxcore.so" for item in mounts):
        mounts.append({"hostPath":"/usr/lib/x86_64-linux-gnu/libdxcore.so","containerPath":"/usr/lib/x86_64-linux-gnu/libdxcore.so","options":["ro","nosuid","nodev","bind"]})
    spec_file = ROOT / ".local/cdi-nvidia.json"
    spec_file.write_text(json.dumps(spec,indent=2))
    subprocess.run(["docker","cp",str(spec_file),CONTEXT+":/etc/cdi/nvidia.yaml"],check=True)
    subprocess.run(["docker","exec","-i",CONTEXT,"tee","/var/run/cdi/nvidia.yaml"],input=json.dumps(spec),capture_output=True,text=True,check=True)
    subprocess.run(["docker","exec",CONTEXT,"nvidia-ctk","config","--set","nvidia-container-runtime.mode=cdi","--in-place"],check=True)
    patch = {"spec":{"template":{"spec":{
        "volumes":[{"name":"wsl-dxcore","hostPath":{"path":"/usr/lib/x86_64-linux-gnu/libdxcore.so","type":"File"}}],
        "containers":[{"name":"nvidia-device-plugin-ctr","env":[{"name":"LD_LIBRARY_PATH","value":"/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/lib/wsl/lib:/usr/lib/x86_64-linux-gnu:/usr/lib"}],"volumeMounts":[{"name":"wsl-dxcore","mountPath":"/usr/lib/wsl/lib/libdxcore.so","readOnly":True}]}]
    }}}}
    patch_file = ROOT / ".local/wsl-device-plugin-patch.json"
    patch_file.write_text(json.dumps(patch))
    kubectl("-n","kube-system","patch","daemonset","nvidia-device-plugin-daemonset","--type=strategic","--patch-file",str(patch_file))
    kubectl("-n","kube-system","rollout","status","daemonset/nvidia-device-plugin-daemonset","--timeout=180s")
    count = 0
    for attempt in range(15):
        node = json.loads(kubectl("get","node",CONTEXT,"-o","json"))
        count = int(node["status"]["allocatable"].get("nvidia.com/gpu",0))
        if count == 1:
            break
        time.sleep(2)
    if count != 1:
        raise RuntimeError("The NVIDIA plugin did not register the GPU.")
    print("The dedicated Kubernetes node exposes one NVIDIA GPU.")

if __name__ == "__main__":
    main()

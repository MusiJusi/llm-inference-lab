"""Record the real GPU backend and reproducible runtime metadata."""
import datetime
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    probe = "import importlib.metadata,json,os,torch; assert os.getuid()==10001; assert torch.cuda.is_available(); result=float((torch.ones(4,device='cuda')*2).sum()); assert result==8; print(json.dumps({'uid':os.getuid(),'vllm':importlib.metadata.version('vllm'),'torch':torch.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0),'compute_capability':torch.cuda.get_device_capability(0),'gpu_memory_bytes':torch.cuda.get_device_properties(0).total_memory,'cuda_computation':'passed'}))"
    result = subprocess.run(["docker", "compose", "exec", "-T", "server", "python3", "-c", probe],cwd=ROOT,capture_output=True,text=True,check=True)
    runtime = json.loads(result.stdout.splitlines()[-1])
    details = json.loads(subprocess.check_output(["docker", "inspect", "llm-inference-lab-server-1"],text=True))[0]
    base = json.loads(subprocess.check_output(["docker", "image", "inspect", json.loads((ROOT/"config/runtime.json").read_text())["base_image"]],text=True))[0]
    report = {"recorded_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"source_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"runtime":runtime,"image_id":details["Image"],"base_image_digests":base.get("RepoDigests",[]),"inference":json.loads((ROOT/'config/inference.json').read_text()),"model":dict(line.split('=',1) for line in (ROOT/'config/model.env').read_text().splitlines() if line and not line.startswith('#')),"deployment":"Docker Compose, Windows / WSL 2, one NVIDIA GPU","limits":{"cpus":6,"memory_gib":12}}
    output=ROOT/'results/environment.json';output.parent.mkdir(exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(runtime,indent=2))

if __name__ == "__main__":
    main()

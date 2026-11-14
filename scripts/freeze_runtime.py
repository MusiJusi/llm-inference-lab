"""Refresh the active Python inventory for the selected immutable base image."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    image=json.loads((ROOT/"config/runtime.json").read_text())["base_image"]
    if "@sha256:" not in image:
        raise ValueError("Use an immutable image digest.")
    probe='import importlib.metadata,json,re; canonical=lambda n:re.sub(r"[-_.]+","-",n).lower(); print(json.dumps({canonical(d.metadata["Name"]):importlib.metadata.version(d.metadata["Name"]) for d in importlib.metadata.distributions()}))'
    packages=json.loads(subprocess.check_output(["docker","run","--rm","--entrypoint","python3",image,"-c",probe],text=True))
    (ROOT/"requirements.txt").write_text("# Active Python distributions; package bytes are pinned by the base OCI image digest.\n"+"".join(name+"=="+version+"\n" for name,version in sorted(packages.items())))
    print(f"Recorded {len(packages)} active runtime packages.")

if __name__=="__main__":
    main()

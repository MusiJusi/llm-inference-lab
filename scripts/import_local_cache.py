"""Seed only this lab PVC from this lab's existing Compose model volume."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from app.model_store import model_location
CONTEXT="llm-inference-lab-gpu"
NAMESPACE="llm-inference-lab"

def main():
    environment={**os.environ,"KUBECONFIG":str(ROOT/".local/kubeconfig")}
    def kubectl(*arguments):
        return subprocess.check_output(["kubectl","--context",CONTEXT,*arguments],env=environment,text=True)
    nodes=json.loads(kubectl("get","nodes","-o","json"))["items"]
    if len(nodes)!=1 or nodes[0]["metadata"]["name"]!=CONTEXT:
        raise RuntimeError("Unexpected cluster; this helper supports only the dedicated lab node.")
    kubectl("apply","-f",str(ROOT/"k8s/base/namespace.yaml"))
    kubectl("-n",NAMESPACE,"apply","-f",str(ROOT/"k8s/base/pvc.yaml"))
    for _ in range(60):
        claim=json.loads(kubectl("-n",NAMESPACE,"get","pvc","model-cache","-o","json"))
        if claim["status"].get("phase")=="Bound":break
        time.sleep(2)
    else:raise TimeoutError("The model PVC did not bind.")
    pv=json.loads(kubectl("get","pv",claim["spec"]["volumeName"],"-o","json"))
    if pv["spec"]["claimRef"]["namespace"]!=NAMESPACE:
        raise RuntimeError("Unexpected PVC namespace.")
    destination=pv["spec"]["hostPath"]["path"]
    if not destination.startswith("/tmp/hostpath-provisioner/"+NAMESPACE+"/") or ".." in destination:
        raise RuntimeError("Unexpected local PVC path.")
    config=dict(line.split("=",1) for line in (ROOT/"config/model.env").read_text().splitlines() if line and not line.startswith("#"))
    model=model_location(Path("/models"),config["MODEL_ID"],config["MODEL_REVISION"]).relative_to("/models").as_posix()
    existing=subprocess.run(["docker","exec",CONTEXT,"test","-e",destination+"/"+model+"/.complete.json"])
    if existing.returncode==0:
        print("The lab PVC already contains this model revision; the init container will validate it.")
        return
    producer=subprocess.Popen(["docker","run","--rm","--network","none","--read-only","--mount","type=volume,src=llm-inference-lab-models,dst=/models,readonly","--entrypoint","tar","llm-inference-lab-downloader:dev","-C","/models","-cf","-",model],stdout=subprocess.PIPE)
    try:
        consumer=subprocess.run(["docker","exec","-i",CONTEXT,"tar","-xf","-","-C",destination],stdin=producer.stdout)
        producer.stdout.close()
        if consumer.returncode!=0 or producer.wait()!=0:
            raise RuntimeError("The local cache transfer failed.")
    finally:
        if producer.poll() is None:
            producer.terminate();producer.wait()
    print("Copied the selected lab model snapshot into the separate lab PVC.")

if __name__=="__main__":main()

"""Load images only when the dedicated node has different layers or configuration."""
import argparse
import json
import subprocess

NODE="llm-inference-lab-gpu"
IMAGES=("llm-inference-lab-downloader:dev","llm-inference-lab:dev")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minikube",default="minikube")
    args=parser.parse_args()
    needed=[]
    for image in IMAGES:
        host=json.loads(subprocess.check_output(["docker","image","inspect",image],text=True))[0]
        result=subprocess.run(["docker","exec",NODE,"docker","image","inspect",image],capture_output=True,text=True)
        node=json.loads(result.stdout)[0] if result.returncode==0 else None
        if node is None or host["Config"]!=node["Config"] or host["RootFS"]!=node["RootFS"]:
            needed.append(image)
    if needed:
        subprocess.run([args.minikube,"image","load","--profile",NODE,*needed],check=True)
    else:
        print("The GPU node already has identical image layers and configuration.")

if __name__=="__main__":main()

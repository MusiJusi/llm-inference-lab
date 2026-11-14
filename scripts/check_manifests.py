"""Check rendered GPU deployment invariants without a running cluster."""
import sys
from pathlib import Path

def check(text):
    required = ('namespace: llm-inference-lab', 'nvidia.com/gpu: "1"', 'runAsNonRoot: true', 'readOnlyRootFilesystem: true', 'claimName: model-cache', 'progressDeadlineSeconds: 1800', 'enableServiceLinks: false')
    for item in required:
        if item not in text:
            raise ValueError("Missing deployment invariant: " + item)
    if 'kaspersky' in text.lower() or 'namespace: llm-inference\n' in text:
        raise ValueError("Deployment must use only the inference-lab resources.")
    print("GPU deployment configuration passed.")

if __name__ == "__main__":
    check(Path(sys.argv[1]).read_text())

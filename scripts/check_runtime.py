"""Verify all installed Python versions against the digest-pinned image inventory."""
import importlib.metadata
import re
import sys
from pathlib import Path

def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()

def verify(path):
    expected = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.split("==", 1)
            expected[canonical(name)] = version
    actual = {canonical(d.metadata["Name"]): importlib.metadata.version(d.metadata["Name"]) for d in importlib.metadata.distributions()}
    if expected != actual:
        changes = sorted(name for name in expected.keys() | actual.keys() if expected.get(name) != actual.get(name))
        raise RuntimeError("Runtime dependency inventory differs: " + ", ".join(changes))
    print(f"Verified {len(expected)} pinned runtime packages.")

if __name__ == "__main__":
    verify(sys.argv[1])

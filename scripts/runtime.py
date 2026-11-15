"""Resolve Compose profiles and validate the model actually running in the lab."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("default", "qwen2.5-1.5b", "qwen3-4b")
CONTAINER = "llm-inference-lab-server-1"


def compose_command(profile="default"):
    if profile not in PROFILES:
        raise ValueError("Unknown inference profile.")
    command = ["docker", "compose", "-f", str(ROOT / "compose.yaml")]
    if profile != "default":
        command.extend(["-f", str(ROOT / "profiles" / profile / "compose.yaml")])
    return command


def compose_configuration(profile="default"):
    return json.loads(subprocess.check_output(
        compose_command(profile) + ["config", "--format", "json"], cwd=ROOT, text=True,
    ))


def inference_settings(configuration):
    mounted = next(volume for volume in configuration["services"]["server"]["volumes"]
                   if volume["target"] == "/config/inference.json")
    return json.loads(Path(mounted["source"]).read_text(encoding="utf-8"))


def model_environment(configuration):
    environment = configuration["services"]["server"]["environment"]
    return {key: environment[key] for key in ("MODEL_ID", "MODEL_REVISION", "MODEL_ROOT")}


def validate_running_model(configuration, details):
    actual = dict(item.split("=", 1) for item in details["Config"]["Env"] if "=" in item)
    expected = model_environment(configuration)
    if any(actual.get(key) != value for key, value in expected.items()):
        raise RuntimeError("The running model does not match the selected Compose profile.")
    if not details["State"]["Running"]:
        raise RuntimeError("The inference container is not running.")
    return expected


def cache_mount_argument(configuration):
    mount = next(volume for volume in configuration["services"]["download-model"]["volumes"]
                 if volume["target"] == "/models")
    source = mount["source"]
    if mount["type"] == "volume":
        source = configuration["volumes"][source]["name"]
    elif mount["type"] != "bind":
        raise ValueError("Unsupported model cache storage.")
    return "type=" + mount["type"] + ",src=" + source + ",dst=/models"


def validate_profiles():
    configurations = {profile: compose_configuration(profile) for profile in PROFILES}
    small = inference_settings(configurations["qwen2.5-1.5b"])
    large = inference_settings(configurations["qwen3-4b"])
    if {key: value for key, value in small.items() if key != "served_model_name"} != {
        key: value for key, value in large.items() if key != "served_model_name"
    }:
        raise ValueError("Comparison profiles must have the same inference limits.")
    for service in ("server", "download-model"):
        mount = next(volume for volume in configurations["qwen3-4b"]["services"][service]["volumes"]
                     if volume["target"] == "/models")
        if mount["type"] != "bind" or Path(mount["source"]).resolve() != (ROOT / "models").resolve():
            raise ValueError("Qwen3 weights must use the project models directory.")
        if service == "server" and not mount.get("read_only"):
            raise ValueError("The server must mount model weights read-only.")
    print("Compose profiles passed: common comparison limits and Qwen3 bind-mounted weights.")


if __name__ == "__main__":
    validate_profiles()

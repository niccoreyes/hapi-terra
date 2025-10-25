import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ENV_FILE = Path(".env")
MIN_K8S_VERSION = "1.29"


def load_env() -> Dict[str, str]:
    values: Dict[str, str] = {}
    if ENV_FILE.exists():
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def save_env(values: Dict[str, str]) -> None:
    lines = [f"{key}={values.get(key, '')}" for key in sorted(values)]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_dependency(name: str, install_command: str) -> None:
    if shutil.which(name):
        return
    print(f"{name} not found. Installing via Chocolatey...")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", install_command],
        check=False,
    )
    if result.returncode != 0 or not shutil.which(name):
        print(f"WARNING: {name} is still unavailable. Install it manually and rerun.")


def set_env_persistent(pairs: Dict[str, str]) -> None:
    for key, value in pairs.items():
        if value is None:
            continue
        subprocess.run(["setx", key, value], check=False)
        os.environ[key] = value


def prompt(message: str, default: str = "", display_default: str = "") -> str:
    suffix = ""
    if default:
        shown = display_default if display_default else default
        suffix = f" [{shown}]"
    response = input(f"{message}{suffix}: ").strip()
    if not response and default:
        return default
    return response


def parse_version(value: str) -> List[int]:
    parts = value.split(".")
    version_numbers: List[int] = []
    for part in parts:
        if not part.isdigit():
            raise ValueError(f"Invalid numeric version segment: {value}")
        version_numbers.append(int(part))
    while len(version_numbers) < 3:
        version_numbers.append(0)
    return version_numbers


def enforce_min_k8s_version(requested: str) -> str:
    candidate = requested or MIN_K8S_VERSION
    try:
        parsed_candidate = parse_version(candidate)
        parsed_min = parse_version(MIN_K8S_VERSION)
    except ValueError:
        print(f'Kubernetes version "{requested}" is invalid. Using {MIN_K8S_VERSION}.')
        return MIN_K8S_VERSION
    if parsed_candidate < parsed_min:
        print(
            f"Kubernetes version {candidate} is below supported minimum "
            f"{MIN_K8S_VERSION}. Using {MIN_K8S_VERSION} instead."
        )
        return MIN_K8S_VERSION
    return candidate


def run_streamed(command: List[str]) -> int:
    process = subprocess.Popen(command, text=True)
    try:
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return process.wait()


def run_captured(command: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def confirm_destruction() -> bool:
    response = input('Type "DESTROY" to continue: ').strip()
    return response.upper() == "DESTROY"


def ensure_python_version() -> None:
    if sys.version_info < (3, 9):
        print("Python 3.9 or later is required for these automation scripts.")
        sys.exit(1)

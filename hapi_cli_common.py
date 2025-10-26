import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ENV_FILE = Path(".env")
# Keep aligned with the highest Kubernetes version Amazon EKS currently supports.
MIN_K8S_VERSION = "1.29"

_RESET = "\033[0m"
_TAG_COLORS = {
    "CMD": "\033[95m",
    "OUT": "\033[92m",
    "ERR": "\033[91m",
    "EXIT": "\033[93m",
}

try:
    if os.name == "nt":
        import colorama

        colorama.just_fix_windows_console()
    _USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR", "")
except ImportError:
    _USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR", "")


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
    rc = run_streamed(
        ["powershell", "-NoProfile", "-Command", install_command]
    )
    if rc != 0 or not shutil.which(name):
        print(f"WARNING: {name} is still unavailable. Install it manually and rerun.")


def set_env_persistent(pairs: Dict[str, str]) -> None:
    for key, value in pairs.items():
        if value is None or value == "":
            continue
        run_streamed(["setx", key, value])
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


def _format_command(command: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def _tag(label: str) -> str:
    color = _TAG_COLORS.get(label)
    if color and _USE_COLOR:
        return f"{color}[{label}]{_RESET}"
    return f"[{label}]"


def run_streamed(command: List[str]) -> int:
    print(f"{_tag('CMD')} {_format_command(command)}", flush=True)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.rstrip("\r\n")
                print(f"{_tag('OUT')} {line}")
    except KeyboardInterrupt:
        process.terminate()
        rc = process.wait()
        print(f"{_tag('EXIT')} {rc}")
        return rc
    finally:
        if process.stdout is not None:
            process.stdout.close()
    rc = process.wait()
    print(f"{_tag('EXIT')} {rc}")
    return rc


def run_captured(command: List[str]) -> subprocess.CompletedProcess:
    print(f"{_tag('CMD')} {_format_command(command)}", flush=True)
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"{_tag('OUT')} {line.rstrip()}")
    if result.stderr:
        for line in result.stderr.splitlines():
            print(f"{_tag('ERR')} {line.rstrip()}")
    print(f"{_tag('EXIT')} {result.returncode}")
    return result


def confirm_destruction() -> bool:
    response = input('Type "DESTROY" to continue: ').strip()
    return response.upper() == "DESTROY"


def ensure_python_version() -> None:
    if sys.version_info < (3, 9):
        print("Python 3.9 or later is required for these automation scripts.")
        sys.exit(1)

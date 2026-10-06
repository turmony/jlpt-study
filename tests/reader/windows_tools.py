"""Keep mocked Windows logic portable and translate paths for real WSL interop."""

import os
import shutil
import subprocess
from pathlib import Path

POWERSHELL_AVAILABLE = bool(
    shutil.which("powershell.exe") and (os.name == "nt" or shutil.which("wslpath"))
)
WSL_AVAILABLE = bool(POWERSHELL_AVAILABLE and os.environ.get("WSL_DISTRO_NAME"))


def windows_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt":
        return resolved
    return subprocess.check_output(["wslpath", "-w", resolved], text=True, encoding="utf-8").strip()


def local_path(path: str) -> Path:
    if os.name == "nt":
        return Path(path)
    converted = subprocess.check_output(["wslpath", "-u", path], text=True, encoding="utf-8").strip()
    return Path(converted)


def run_powershell(script: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", windows_path(script), *arguments],
        capture_output=True, text=True, encoding="utf-8", timeout=30, check=True,
    )

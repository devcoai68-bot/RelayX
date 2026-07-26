"""Environment capture for reproducible RelayX benchmark baselines."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import subprocess  # nosec B404: benchmark metadata uses subprocess with a resolved executable and shell disabled.
from pathlib import Path
from typing import Any

from benchmarks.common import format_bytes

_PACKAGES = (
    "fastapi",
    "uvicorn",
    "httpx",
    "cryptography",
    "msgpack",
    "zstandard",
    "pydantic-settings",
)


def capture_environment(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    return {
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu": _cpu_name(),
        "cpu_count": os.cpu_count(),
        "ram": format_bytes(_total_ram_bytes()),
        "python": platform.python_version(),
        "packages": _package_versions(),
        "relayx_git_commit": _git_commit(repo_root),
    }


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in _PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _git_commit(repo_root: Path) -> str:
    git_executable = shutil.which("git")
    if git_executable is None:
        return "unknown"

    try:
        completed = subprocess.run(
            [git_executable, "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )  # nosec B603: git_executable is resolved by shutil.which(), arguments are fixed, and shell is disabled.
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip()


def _cpu_name() -> str:
    processor = platform.processor()
    if processor:
        return processor
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(errors="ignore").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    return "unknown"


def _total_ram_bytes() -> int:
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text(errors="ignore").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return int(pages * page_size)
        except (OSError, ValueError):
            pass
    return 0

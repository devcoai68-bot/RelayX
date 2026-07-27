"""Operational helpers for RelayX CLI installation and diagnostics."""

from __future__ import annotations

import base64
import importlib.metadata
import os
import platform
import re
import secrets
import shutil
import ssl
import subprocess  # nosec B404 - subprocess is used with absolute executables and shell=False.
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from relayx import __version__
from relayx.config import RelaySettings
from relayx.crypto.keys import decode_encryption_key
from relayx.errors import ConfigError

DEFAULT_SERVICE_NAME = "relayx"
DEFAULT_UNIT_DIR = Path("/etc/systemd/system")
DEFAULT_WORKING_DIRECTORY = Path("/var/lib/relayx")
DEFAULT_ENVIRONMENT_FILE = Path("/etc/relayx/relayx.env")
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")
_SAFE_ACCOUNT_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class SecretBundle:
    auth_token: str
    encryption_key: str


def generate_secrets() -> SecretBundle:
    """Generate independent production secrets using a CSPRNG."""
    return SecretBundle(
        auth_token=secrets.token_urlsafe(48),
        encryption_key=base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
    )


def validate_service_name(value: str) -> str:
    if not _SAFE_NAME_RE.fullmatch(value) or value.startswith("-"):
        raise ValueError(
            "service names may contain only letters, numbers, '.', '_', '@', and '-'"
        )
    return value


def validate_account_name(value: str, label: str) -> str:
    if not _SAFE_ACCOUNT_RE.fullmatch(value):
        raise ValueError(f"{label} must be a valid system account name")
    return value


def _resolve_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise FileNotFoundError(f"required executable not found: {name}")
    return executable


def _relayx_exec_start() -> str:
    relayx = shutil.which("relayx")
    if relayx:
        return f"{relayx} server"
    return f"{sys.executable} -m relayx.cli server"


def env_template(
    *,
    server_host: str = "127.0.0.1",
    server_port: int = 8000,
    auth_token: str | None = None,
    encryption_key: str | None = None,
    log_level: str = "INFO",
    generate_missing_secrets: bool = False,
) -> str:
    if generate_missing_secrets and (not auth_token or not encryption_key):
        generated = generate_secrets()
        auth_token = auth_token or generated.auth_token
        encryption_key = encryption_key or generated.encryption_key
    auth_token = auth_token or "change-me-generate-with-relayx-generate-secret"
    encryption_key = encryption_key or "change-me-base64-32-byte-key"
    lines = [
        "# RelayX production environment file",
        f"RELAYX_AUTH_TOKEN={auth_token}",
        f"RELAYX_ENCRYPTION_KEY={encryption_key}",
        "RELAYX_RELAY_URL=http://127.0.0.1:8000/relay",
        "RELAYX_PROXY_HOST=127.0.0.1",
        "RELAYX_PROXY_PORT=8080",
        f"RELAYX_SERVER_HOST={server_host}",
        f"RELAYX_SERVER_PORT={server_port}",
        "RELAYX_REPLAY_WINDOW_SECONDS=300",
        "RELAYX_ALLOWED_CLOCK_SKEW_SECONDS=30",
        "RELAYX_REPLAY_CACHE_MAX_ENTRIES=1000000",
        "RELAYX_COMPRESSION_ENABLED=true",
        "RELAYX_COMPRESSION_THRESHOLD_BYTES=1024",
        "RELAYX_MAX_DECOMPRESSED_BYTES=134217728",
        "RELAYX_MAX_CARRIER_BODY_BYTES=134217728",
        "RELAYX_MAX_REQUEST_BODY_BYTES=16777216",
        "RELAYX_MAX_RESPONSE_BODY_BYTES=67108864",
        "RELAYX_MAX_HEADER_BYTES=65536",
        "RELAYX_TIMEOUT_SECONDS=30.0",
        f"RELAYX_LOG_LEVEL={log_level.upper()}",
        "",
    ]
    return "\n".join(lines)


def write_env_file(path: Path, content: str, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; use --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    try:
        path.chmod(0o600)
    except PermissionError as exc:
        raise PermissionError(f"unable to set secure permissions on {path}") from exc


def systemd_unit(
    *,
    service_name: str = DEFAULT_SERVICE_NAME,
    user: str = "relayx",
    group: str = "relayx",
    host: str | None = None,
    port: int | None = None,
    config: str | None = None,
    auth_token: str | None = None,
    encryption_key: str | None = None,
    working_directory: str | Path = DEFAULT_WORKING_DIRECTORY,
    environment_file: str | Path | None = DEFAULT_ENVIRONMENT_FILE,
    memory_max: str | None = None,
) -> str:
    validate_service_name(service_name)
    validate_account_name(user, "user")
    validate_account_name(group, "group")
    env_parts = []
    if host:
        env_parts.append(f"RELAYX_SERVER_HOST={host}")
    if port:
        env_parts.append(f"RELAYX_SERVER_PORT={port}")
    if config:
        env_parts.append(f"RELAYX_CONFIG={config}")
    if auth_token:
        env_parts.append(f"RELAYX_AUTH_TOKEN={auth_token}")
    if encryption_key:
        env_parts.append(f"RELAYX_ENCRYPTION_KEY={encryption_key}")
    env_line = ""
    if env_parts:
        env_line = 'Environment="' + '" "'.join(env_parts) + '"\n'
    env_file_line = f"EnvironmentFile=-{environment_file}\n" if environment_file else ""
    memory_line = f"MemoryMax={memory_max}\n" if memory_max else ""
    return f"""[Unit]
Description=RelayX encrypted HTTP relay ({service_name})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={group}
WorkingDirectory={working_directory}
{env_file_line}{env_line}ExecStart={_relayx_exec_start()}
Restart=on-failure
RestartSec=5s
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={working_directory}
ReadOnlyPaths=/etc/relayx
RuntimeDirectory={service_name}
RuntimeDirectoryMode=0750
LimitNOFILE=65536
{memory_line}TasksMax=512
CapabilityBoundingSet=
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictRealtime=true
SystemCallArchitectures=native

[Install]
WantedBy=multi-user.target
"""


def run_commands(commands: Iterable[list[str]], *, dry_run: bool = False) -> list[str]:
    rendered: list[str] = []
    for command in commands:
        rendered.append(" ".join(command))
        if not dry_run:
            subprocess.run(
                command, check=True
            )  # nosec B603 - validated absolute argv, shell=False.
    return rendered


def _service_unit_name(service_name: str) -> str:
    return f"{validate_service_name(service_name)}.service"


def install_service(
    *,
    unit_text: str,
    service_name: str,
    user: str,
    group: str,
    working_directory: Path,
    unit_dir: Path = DEFAULT_UNIT_DIR,
    create_user: bool = False,
    start: bool = False,
    dry_run: bool = False,
) -> list[str]:
    service_name = validate_service_name(service_name)
    user = validate_account_name(user, "user")
    validate_account_name(group, "group")
    systemctl = _resolve_executable("systemctl")
    commands: list[list[str]] = []
    if create_user:
        id_executable = _resolve_executable("id")
        useradd = _resolve_executable("useradd")
        user_exists = False
        if not dry_run:
            result = subprocess.run(  # nosec B603 - absolute executable, validated user, shell=False.
                [id_executable, "-u", user],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            user_exists = result.returncode == 0
        if dry_run or not user_exists:
            commands.append(
                [
                    useradd,
                    "--system",
                    "--home-dir",
                    str(working_directory),
                    "--shell",
                    "/usr/sbin/nologin",
                    "--user-group",
                    user,
                ]
            )
    unit_path = unit_dir / _service_unit_name(service_name)
    actions = [f"write {unit_path}\n{unit_text}"]
    if not dry_run:
        working_directory.mkdir(parents=True, exist_ok=True)
        unit_dir.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(unit_text, encoding="utf-8")
    commands.extend(
        [
            [systemctl, "daemon-reload"],
            [systemctl, "enable", _service_unit_name(service_name)],
        ]
    )
    if start:
        commands.append([systemctl, "start", _service_unit_name(service_name)])
    return actions + run_commands(commands, dry_run=dry_run)


def uninstall_service(
    *,
    service_name: str,
    unit_dir: Path = DEFAULT_UNIT_DIR,
    purge_paths: Iterable[Path] = (),
    purge: bool = False,
    dry_run: bool = False,
) -> list[str]:
    service_name = validate_service_name(service_name)
    systemctl = _resolve_executable("systemctl")
    unit_path = unit_dir / _service_unit_name(service_name)
    actions = run_commands(
        [
            [systemctl, "stop", _service_unit_name(service_name)],
            [systemctl, "disable", _service_unit_name(service_name)],
        ],
        dry_run=dry_run,
    )
    actions.append(f"remove {unit_path}")
    if not dry_run and unit_path.exists():
        unit_path.unlink()
    actions += run_commands([[systemctl, "daemon-reload"]], dry_run=dry_run)
    if purge:
        for path in purge_paths:
            actions.append(f"purge {path}")
            if not dry_run and path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
    return actions


def service_action(*, service_name: str, action: str) -> int:
    if action not in {"status", "restart", "stop", "start"}:
        raise ValueError("unsupported service action")
    systemctl = _resolve_executable("systemctl")
    result = subprocess.run(  # nosec B603 - absolute executable, validated action/name, shell=False.
        [systemctl, action, _service_unit_name(service_name)], check=False
    )
    return result.returncode


def validate_settings(env_file: Path | None = None) -> tuple[bool, str]:
    try:
        RelaySettings(_env_file=env_file) if env_file else RelaySettings()
    except (ValidationError, ValueError) as exc:
        return False, str(exc)
    return True, "configuration is valid"


def version_info() -> str:
    commit = "unknown"
    git = shutil.which("git")
    if git:
        try:
            commit = subprocess.check_output(  # nosec B603 - absolute executable, static argv, shell=False.
                [git, "rev-parse", "--short", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, OSError):
            commit = "unknown"
    return "\n".join(
        [
            f"RelayX version: {__version__}",
            f"Python version: {platform.python_version()}",
            f"OpenSSL version: {ssl.OPENSSL_VERSION}",
            f"Git commit: {commit}",
            f"Platform: {platform.platform()}",
        ]
    )


def _read_env_values(env_file: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_file and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


def doctor(env_file: Path | None = None) -> list[tuple[str, str, str]]:
    checks: list[tuple[str, str, str]] = []
    env_values = _read_env_values(env_file)
    checks.append(
        (
            "PASS" if sys.version_info >= (3, 12) else "ERROR",
            "Python",
            platform.python_version(),
        )
    )
    checks.append(("PASS", "OpenSSL", ssl.OPENSSL_VERSION))
    for package in ["cryptography", "httpx", "fastapi", "msgpack", "zstandard"]:
        try:
            version = importlib.metadata.version(package)
            checks.append(("PASS", package, version))
        except importlib.metadata.PackageNotFoundError:
            checks.append(("ERROR", package, "not installed"))
    valid, message = validate_settings(env_file)
    checks.append(("PASS" if valid else "ERROR", "config", message.splitlines()[0]))
    token = os.environ.get("RELAYX_AUTH_TOKEN") or env_values.get("RELAYX_AUTH_TOKEN")
    checks.append(
        (
            "PASS" if token and len(token) >= 16 else "WARNING",
            "auth token",
            "set" if token else "not set",
        )
    )
    key = os.environ.get("RELAYX_ENCRYPTION_KEY") or env_values.get(
        "RELAYX_ENCRYPTION_KEY"
    )
    try:
        decode_encryption_key(key or "")
        checks.append(("PASS", "encryption key", "32 bytes"))
    except (ConfigError, ValueError, TypeError) as exc:
        checks.append(("ERROR", "encryption key", str(exc)))
    cwd = Path.cwd()
    checks.append(
        ("PASS" if os.access(cwd, os.W_OK) else "WARNING", "writable cwd", str(cwd))
    )
    checks.append(
        (
            "PASS" if shutil.which("systemctl") else "WARNING",
            "systemd",
            shutil.which("systemctl") or "not found",
        )
    )
    checks.append(
        (
            "PASS" if shutil.which("docker") else "WARNING",
            "Docker",
            shutil.which("docker") or "not found",
        )
    )
    checks.append(
        (
            "PASS" if shutil.which("nginx") else "WARNING",
            "nginx",
            shutil.which("nginx") or "not found",
        )
    )
    return checks

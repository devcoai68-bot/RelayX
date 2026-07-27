"""Operational helpers for RelayX CLI installation and diagnostics."""

from __future__ import annotations

import base64
import importlib.metadata
import os
import platform
import secrets
import shutil
import ssl
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from relayx import __version__
from relayx.config import RelaySettings
from relayx.crypto.keys import decode_encryption_key

DEFAULT_SERVICE_NAME = "relayx"
DEFAULT_UNIT_DIR = Path("/etc/systemd/system")
DEFAULT_WORKING_DIRECTORY = Path("/var/lib/relayx")
DEFAULT_ENVIRONMENT_FILE = Path("/etc/relayx/relayx.env")


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
    except PermissionError:
        pass


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
) -> str:
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
    return f"""[Unit]
Description=RelayX encrypted HTTP relay ({service_name})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={group}
WorkingDirectory={working_directory}
{env_file_line}{env_line}ExecStart={shutil.which('relayx') or sys.executable + ' -m relayx.cli'} server
Restart=on-failure
RestartSec=5s
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={working_directory}
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
            subprocess.run(command, check=True)
    return rendered


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
    unit_path = unit_dir / f"{service_name}.service"
    actions = [f"write {unit_path}\n{unit_text}"]
    commands: list[list[str]] = []
    if create_user:
        commands.append(
            [
                "sh",
                "-c",
                f"id -u {user} >/dev/null 2>&1 || useradd --system --home-dir {working_directory} --shell /usr/sbin/nologin --user-group {user}",
            ]
        )
    if not dry_run:
        working_directory.mkdir(parents=True, exist_ok=True)
        unit_dir.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(unit_text, encoding="utf-8")
    commands.extend(
        [
            ["systemctl", "daemon-reload"],
            ["systemctl", "enable", f"{service_name}.service"],
        ]
    )
    if start:
        commands.append(["systemctl", "start", f"{service_name}.service"])
    return actions + run_commands(commands, dry_run=dry_run)


def uninstall_service(
    *,
    service_name: str,
    unit_dir: Path = DEFAULT_UNIT_DIR,
    purge_paths: Iterable[Path] = (),
    purge: bool = False,
    dry_run: bool = False,
) -> list[str]:
    unit_path = unit_dir / f"{service_name}.service"
    actions = run_commands(
        [
            ["systemctl", "stop", f"{service_name}.service"],
            ["systemctl", "disable", f"{service_name}.service"],
        ],
        dry_run=dry_run,
    )
    actions.append(f"remove {unit_path}")
    if not dry_run and unit_path.exists():
        unit_path.unlink()
    actions += run_commands([["systemctl", "daemon-reload"]], dry_run=dry_run)
    if purge:
        for path in purge_paths:
            actions.append(f"purge {path}")
            if not dry_run and path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
    return actions


def validate_settings(env_file: Path | None = None) -> tuple[bool, str]:
    try:
        RelaySettings(_env_file=env_file) if env_file else RelaySettings()
    except (ValidationError, ValueError) as exc:
        return False, str(exc)
    return True, "configuration is valid"


def version_info() -> str:
    commit = "unknown"
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass
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
    except Exception as exc:
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

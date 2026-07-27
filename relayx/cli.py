"""RelayX command line interface."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import uvicorn

from relayx.client.app import create_proxy
from relayx.config import RelaySettings
from relayx.logging import configure_logging
from relayx.ops import (
    DEFAULT_ENVIRONMENT_FILE,
    DEFAULT_SERVICE_NAME,
    DEFAULT_UNIT_DIR,
    DEFAULT_WORKING_DIRECTORY,
    doctor,
    env_template,
    generate_secrets,
    install_service,
    systemd_unit,
    uninstall_service,
    validate_settings,
    version_info,
    write_env_file,
)
from relayx.server.app import create_app


async def _run_client(settings: RelaySettings) -> None:
    proxy = await create_proxy(settings)
    server = await proxy.serve()
    async with server:
        await server.serve_forever()


def _settings_from_args(args: argparse.Namespace) -> RelaySettings:
    env_file = getattr(args, "config", None)
    return RelaySettings(_env_file=env_file) if env_file else RelaySettings()


def _run_server(args: argparse.Namespace) -> None:
    settings = _settings_from_args(args)
    configure_logging(settings.log_level)
    uvicorn.run(
        create_app(settings),
        host=settings.server_host,
        port=settings.server_port,
        http="h11",
    )


def _run_client_cmd(args: argparse.Namespace) -> None:
    settings = _settings_from_args(args)
    configure_logging(settings.log_level)
    asyncio.run(_run_client(settings))


def _print_actions(actions: list[str]) -> None:
    for action in actions:
        print(action)


def _cmd_generate_secret(_: argparse.Namespace) -> None:
    bundle = generate_secrets()
    print("Auth Token:")
    print(bundle.auth_token)
    print("\nEncryption Key:")
    print(bundle.encryption_key)


def _cmd_config_init(args: argparse.Namespace) -> None:
    host = args.host or (
        input("Bind address [127.0.0.1]: ").strip() or "127.0.0.1"
        if args.interactive
        else "127.0.0.1"
    )
    port = args.port or (
        int(input("Port [8000]: ").strip() or "8000") if args.interactive else 8000
    )
    auth_token = args.auth_token
    encryption_key = args.encryption_key
    if args.interactive and not args.generate_secrets:
        auth_token = auth_token or input("Auth token: ").strip()
        encryption_key = (
            encryption_key or input("Encryption key (base64 32 bytes): ").strip()
        )
    log_level = args.log_level or (
        input("Log level [INFO]: ").strip() or "INFO" if args.interactive else "INFO"
    )
    content = env_template(
        server_host=host,
        server_port=port,
        auth_token=auth_token,
        encryption_key=encryption_key,
        log_level=log_level,
        generate_missing_secrets=args.generate_secrets,
    )
    if args.dry_run:
        print(content)
        return
    write_env_file(Path(args.output), content, overwrite=args.force)
    print(f"Wrote {args.output}")


def _cmd_config_show(args: argparse.Namespace) -> None:
    settings = _settings_from_args(args)
    for key, value in settings.model_dump().items():
        if "token" in key or "key" in key:
            value = "********"
        print(f"RELAYX_{key.upper()}={value}")


def _cmd_config_validate(args: argparse.Namespace) -> None:
    valid, message = validate_settings(Path(args.config) if args.config else None)
    print(("PASS" if valid else "ERROR") + f": {message}")
    raise SystemExit(0 if valid else 1)


def _cmd_install_service(args: argparse.Namespace) -> None:
    unit = systemd_unit(
        service_name=args.service_name,
        user=args.user,
        group=args.group,
        host=args.host,
        port=args.port,
        config=args.config,
        auth_token=args.auth_token,
        encryption_key=args.encryption_key,
        working_directory=args.working_directory,
        environment_file=args.environment_file,
    )
    actions = install_service(
        unit_text=unit,
        service_name=args.service_name,
        user=args.user,
        group=args.group,
        working_directory=Path(args.working_directory),
        unit_dir=Path(args.unit_dir),
        create_user=args.create_user,
        start=args.start,
        dry_run=args.dry_run,
    )
    _print_actions(actions)


def _cmd_uninstall_service(args: argparse.Namespace) -> None:
    actions = uninstall_service(
        service_name=args.service_name,
        unit_dir=Path(args.unit_dir),
        purge_paths=[Path(args.environment_file), Path(args.working_directory)],
        purge=args.purge,
        dry_run=args.dry_run,
    )
    _print_actions(actions)


def _cmd_service(args: argparse.Namespace) -> None:
    import subprocess

    subprocess.run(
        ["systemctl", args.action, f"{args.service_name}.service"], check=False
    )


def _cmd_doctor(args: argparse.Namespace) -> None:
    for status, name, detail in doctor(Path(args.config) if args.config else None):
        print(f"{status}: {name} - {detail}")


def _cmd_version(_: argparse.Namespace) -> None:
    print(version_info())


def _cmd_init(args: argparse.Namespace) -> None:
    output = Path(args.output)
    content = env_template(
        server_host=args.host, server_port=args.port, generate_missing_secrets=True
    )
    if args.dry_run:
        print(content)
    else:
        write_env_file(output, content, overwrite=args.force)
        print(f"Wrote {output}")
    print("Next steps:")
    print(f"  relayx config validate --config {output}")
    print(f"  relayx server --config {output}")
    print(f"  relayx install service --environment-file {output} --start")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relayx")
    sub = parser.add_subparsers(dest="command")
    for mode, func in [("server", _run_server), ("client", _run_client_cmd)]:
        p = sub.add_parser(mode)
        p.add_argument("--config")
        p.set_defaults(func=func)
    p = sub.add_parser("generate-secret")
    p.set_defaults(func=_cmd_generate_secret)
    p = sub.add_parser("version")
    p.set_defaults(func=_cmd_version)
    p = sub.add_parser("doctor")
    p.add_argument("--config")
    p.set_defaults(func=_cmd_doctor)
    p = sub.add_parser("init")
    p.add_argument("--output", default=".env")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cmd_init)

    config = sub.add_parser("config").add_subparsers(
        dest="config_command", required=True
    )
    p = config.add_parser("init")
    p.add_argument("--output", default=".env")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--auth-token")
    p.add_argument("--encryption-key")
    p.add_argument("--log-level")
    p.add_argument("--generate-secrets", action="store_true")
    p.add_argument("--interactive", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cmd_config_init)
    p = config.add_parser("show")
    p.add_argument("--config")
    p.set_defaults(func=_cmd_config_show)
    p = config.add_parser("validate")
    p.add_argument("--config")
    p.set_defaults(func=_cmd_config_validate)

    install = sub.add_parser("install").add_subparsers(
        dest="install_command", required=True
    )
    p = install.add_parser("service")
    p.add_argument("--user", default="relayx")
    p.add_argument("--group", default="relayx")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--config")
    p.add_argument("--auth-token")
    p.add_argument("--encryption-key")
    p.add_argument("--working-directory", default=str(DEFAULT_WORKING_DIRECTORY))
    p.add_argument("--environment-file", default=str(DEFAULT_ENVIRONMENT_FILE))
    p.add_argument("--service-name", default=DEFAULT_SERVICE_NAME)
    p.add_argument("--unit-dir", default=str(DEFAULT_UNIT_DIR))
    p.add_argument("--create-user", action="store_true")
    p.add_argument("--start", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cmd_install_service)

    uninstall = sub.add_parser("uninstall").add_subparsers(
        dest="uninstall_command", required=True
    )
    p = uninstall.add_parser("service")
    p.add_argument("--service-name", default=DEFAULT_SERVICE_NAME)
    p.add_argument("--unit-dir", default=str(DEFAULT_UNIT_DIR))
    p.add_argument("--environment-file", default=str(DEFAULT_ENVIRONMENT_FILE))
    p.add_argument("--working-directory", default=str(DEFAULT_WORKING_DIRECTORY))
    p.add_argument("--purge", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cmd_uninstall_service)

    service = sub.add_parser("service").add_subparsers(dest="action", required=True)
    for action in ["status", "restart", "stop", "start"]:
        p = service.add_parser(action)
        p.add_argument("--service-name", default=DEFAULT_SERVICE_NAME)
        p.set_defaults(func=_cmd_service, action=action)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        raise SystemExit(2)
    args.func(args)


if __name__ == "__main__":
    main()

from __future__ import annotations

import base64

from relayx.cli import build_parser
from relayx.ops import (
    doctor,
    env_template,
    generate_secrets,
    systemd_unit,
    validate_service_name,
    validate_settings,
)


def test_secret_generation_is_valid_and_distinct():
    bundle = generate_secrets()
    assert len(bundle.auth_token) >= 32
    assert base64.b64decode(bundle.encryption_key, validate=True)
    assert len(base64.b64decode(bundle.encryption_key)) == 32
    assert bundle.auth_token != bundle.encryption_key


def test_env_template_generates_valid_config(tmp_path):
    env_file = tmp_path / "relayx.env"
    env_file.write_text(
        env_template(server_port=8179, generate_missing_secrets=True), encoding="utf-8"
    )
    valid, message = validate_settings(env_file)
    assert valid, message


def test_systemd_unit_contains_hardening_and_options():
    unit = systemd_unit(
        service_name="relayx-test",
        user="relayx",
        group="relayx",
        host="0.0.0.0",
        port=8179,
        working_directory="/tmp/relayx",
        environment_file="/tmp/relayx.env",
        memory_max="512M",
    )
    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "RELAYX_SERVER_HOST=0.0.0.0" in unit
    assert "RELAYX_SERVER_PORT=8179" in unit
    assert "EnvironmentFile=-/tmp/relayx.env" in unit
    assert "ReadOnlyPaths=/etc/relayx" in unit
    assert "RuntimeDirectory=relayx-test" in unit
    assert "LimitNOFILE=65536" in unit
    assert "TasksMax=512" in unit
    assert "MemoryMax=512M" in unit


def test_cli_parses_backward_compatible_modes():
    parser = build_parser()
    assert parser.parse_args(["server"]).command == "server"
    assert parser.parse_args(["client"]).command == "client"
    assert (
        parser.parse_args(["install", "service", "--dry-run"]).install_command
        == "service"
    )


def test_config_init_dry_run_outputs_env(capsys):
    parser = build_parser()
    args = parser.parse_args(
        ["config", "init", "--generate-secrets", "--dry-run", "--port", "8179"]
    )
    args.func(args)
    out = capsys.readouterr().out
    assert "RELAYX_SERVER_PORT=8179" in out
    assert "RELAYX_AUTH_TOKEN=" in out


def test_doctor_output_has_statuses():
    statuses = {status for status, _, _ in doctor()}
    assert statuses <= {"PASS", "WARNING", "ERROR"}


def test_service_name_validation_rejects_unsafe_values():
    assert validate_service_name("relayx-prod") == "relayx-prod"
    for value in ["", "../../bad", "bad service", "-bad"]:
        try:
            validate_service_name(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted unsafe service name: {value}")

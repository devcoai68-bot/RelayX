"""RelayX settings."""

from __future__ import annotations

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from relayx.constants import *
from relayx.crypto.keys import decode_encryption_key


class RelaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RELAYX_")
    auth_token: str
    encryption_key: str
    relay_url: str = "http://127.0.0.1:8000/relay"
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 8080
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    replay_window_seconds: int = DEFAULT_REPLAY_WINDOW_SECONDS
    allowed_clock_skew_seconds: int = DEFAULT_ALLOWED_CLOCK_SKEW_SECONDS
    replay_cache_max_entries: int = DEFAULT_REPLAY_CACHE_MAX_ENTRIES
    compression_enabled: bool = True
    compression_threshold_bytes: int = DEFAULT_COMPRESSION_THRESHOLD_BYTES
    max_decompressed_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES
    max_carrier_body_bytes: int = DEFAULT_MAX_CARRIER_BODY_BYTES
    max_request_body_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES
    max_response_body_bytes: int = DEFAULT_MAX_RESPONSE_BODY_BYTES
    max_header_bytes: int = DEFAULT_MAX_HEADER_BYTES
    timeout_seconds: float = 30.0
    log_level: str = "INFO"

    @field_validator("auth_token", "encryption_key")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("secret values must not be empty")
        return value

    @field_validator("proxy_port", "server_port")
    @classmethod
    def _valid_port(cls, value: int) -> int:
        if not (1 <= value <= 65535):
            raise ValueError("ports must be between 1 and 65535")
        return value

    @field_validator(
        "replay_window_seconds",
        "replay_cache_max_entries",
        "max_decompressed_bytes",
        "max_carrier_body_bytes",
        "max_request_body_bytes",
        "max_response_body_bytes",
        "max_header_bytes",
    )
    @classmethod
    def _positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("setting must be positive")
        return value

    @field_validator("allowed_clock_skew_seconds", "compression_threshold_bytes")
    @classmethod
    def _non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("setting must be non-negative")
        return value

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(
                "log level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
            )
        return normalized

    @field_validator("timeout_seconds")
    @classmethod
    def _positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("timeout must be positive")
        return value

    @model_validator(mode="after")
    def _separate_secrets(self) -> "RelaySettings":
        if self.auth_token == self.encryption_key:
            raise ValueError(
                "RELAYX_AUTH_TOKEN and RELAYX_ENCRYPTION_KEY must be different"
            )
        return self

    @property
    def encryption_key_bytes(self) -> bytes:
        return decode_encryption_key(self.encryption_key)

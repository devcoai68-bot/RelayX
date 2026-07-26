"""Structured logging helpers for RelayX."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping
from typing import Any

_SECRET_FIELDS = {
    "authorization",
    "auth_token",
    "encryption_key",
    "token",
    "key",
    "body",
    "request_body",
    "response_body",
}


class JsonFormatter(logging.Formatter):
    """Small JSON formatter that avoids logging sensitive fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "relayx", None)
        if isinstance(extra, Mapping):
            payload.update(_sanitize(extra))
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _sanitize(values: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in values.items():
        key_text = str(key)
        if key_text.lower() in _SECRET_FIELDS:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key_text] = value
        else:
            sanitized[key_text] = str(value)
    return sanitized


def configure_logging(level: str = "INFO") -> None:
    """Configure process-wide structured logging."""

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)
